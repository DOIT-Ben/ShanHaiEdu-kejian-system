import { expect, test, type Page } from "@playwright/test";
import axe from "axe-core";
import { readFile } from "node:fs/promises";
import { loginAsTeacher } from "./support/auth";

const engineeringCopy =
  /生成指令|高级设置|候选|正在渲染|批次创作|局部重试|文件合同|mock|debug|todo|验收/i;

async function openReadyImageStudio(page: Page) {
  await loginAsTeacher(page);
  await page.goto("/app/creation/images");
  await page.getByRole("button", { name: "开始创作图片" }).click();
  await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();
}

async function chooseSelect(page: Page, label: string, option: string) {
  const combobox = page.getByRole("combobox", { name: label });
  if (!(await combobox.isVisible())) {
    await page.getByRole("button", { name: "创作设置" }).click();
  }
  await combobox.click();
  await page.getByRole("option", { name: option }).click();
}

function webpDimensions(content: Buffer) {
  expect(content.subarray(0, 4).toString("ascii")).toBe("RIFF");
  expect(content.subarray(8, 12).toString("ascii")).toBe("WEBP");
  const format = content.subarray(12, 16).toString("ascii");
  if (format === "VP8 ") {
    return {
      height: content.readUInt16LE(28) & 0x3fff,
      width: content.readUInt16LE(26) & 0x3fff,
    };
  }
  if (format === "VP8L") {
    return {
      height:
        1 +
        (((content[24] ?? 0) & 0x0f) << 10) +
        ((content[23] ?? 0) << 2) +
        (((content[22] ?? 0) & 0xc0) >> 6),
      width: 1 + (((content[22] ?? 0) & 0x3f) << 8) + (content[21] ?? 0),
    };
  }
  if (format === "VP8X") {
    return {
      height: 1 + content.readUIntLE(27, 3),
      width: 1 + content.readUIntLE(24, 3),
    };
  }
  throw new Error(`无法识别 WebP 编码：${format}`);
}

async function expectNoA11yViolations(page: Page) {
  await page.addScriptTag({ content: axe.source });
  const violations = await page.evaluate(async () => {
    const result = await (window as typeof window & { axe: typeof axe }).axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
    });
    return result.violations.map(({ help, id, impact, nodes }) => ({
      help,
      id,
      impact,
      nodes: nodes.map((node) => node.html),
    }));
  });
  expect(violations).toEqual([]);
}

test("新老师可按首页引导进入并在需要时调整创作设置", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation");
  await expect(page.locator("body")).not.toContainText(engineeringCopy);
  await expect(page.getByText("第一次使用？建议先画一张教学图片")).toBeVisible();
  await page.getByRole("link", { name: "去画一张" }).click();
  await expect(page.getByText("正在打开课堂作品")).toBeHidden({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "图片创作台" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("等待开始创作", { exact: true })).toHaveCount(0);
  await expect(page.getByText("本地草稿已保存", { exact: true })).toHaveCount(0);

  const description = page.getByLabel("画面内容");
  await expect(page.getByRole("combobox", { name: "创作模型" })).toHaveCount(0);
  await description.fill("三瓶果汁摆在木桌上，画面右侧保留课堂提问空间。");
  await chooseSelect(page, "创作模型", "细节增强");
  const value = await description.inputValue();
  await page.reload();
  await expect(page.getByLabel("画面内容")).toHaveValue(value);
  await expect(page.getByRole("combobox", { name: "创作模型" })).toHaveCount(0);
  await page.getByRole("button", { name: "创作设置" }).click();
  await expect(page.getByRole("combobox", { name: "创作模型" })).toContainText("细节增强");
});

test("项目多作品页面只展示教师需要的操作和下一步", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/batches/mock-batch");
  await expect(page.getByText(/先比较下面三张作品/)).toBeVisible();
  await expect(page.locator("body")).not.toContainText(engineeringCopy);
  await page.getByRole("button", { name: /三张.*标签并排/ }).click();
  await expect(page.getByText(/先点击“重新制作这张”/)).toBeVisible();
});

test("图片、视频和 PPT 共用上下式创作布局", async ({ page }) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await loginAsTeacher(page);
  for (const studio of [
    { input: "画面内容", path: "/app/creation/images" },
    { input: "画面怎样变化", path: "/app/creation/videos" },
    { input: "课件主题与课堂用途", path: "/app/creation/presentations" },
  ]) {
    await page.goto(studio.path);
    await expect(page.locator("main")).toHaveCount(1);
    await expect(page.locator("h1")).toHaveCount(1);
    const outputBox = await page.getByTestId("creation-output-region").boundingBox();
    const composerBox = await page.getByTestId("creation-composer-panel").boundingBox();
    expect(outputBox).not.toBeNull();
    expect(composerBox).not.toBeNull();
    expect(composerBox?.y ?? 0).toBeGreaterThan(outputBox?.y ?? 0);
    await expect(page.getByRole("textbox", { name: studio.input })).toBeInViewport();
    await expect(page.getByRole("button", { name: "上传参考图" })).toBeInViewport();
    await expect(page.getByRole("button", { name: "创作设置" })).toBeInViewport();
    await expect(page.getByRole("combobox", { name: "创作模型" })).toHaveCount(0);
    if (studio.path === "/app/creation/images") {
      await expect(page.getByRole("combobox", { name: "图片比例" })).toBeInViewport();
    }
    await page.getByRole("button", { name: "创作设置" }).click();
    await expect(page.getByLabel("创作模型")).toBeInViewport();
    if (studio.path === "/app/creation/images") {
      await expect(page.getByLabel("比例", { exact: true })).toHaveCount(0);
    } else {
      await expect(page.getByLabel("比例", { exact: true })).toBeInViewport();
    }
    await page.getByRole("button", { name: "创作设置" }).click();
  }
});

test("图片结果可修改创作要求并经过稳定运行态重新创作", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/images");
  await page.getByRole("button", { name: "开始创作图片" }).click();

  const workspace = page.getByRole("region", { name: "创作结果" });
  await expect(workspace).toHaveAttribute("aria-busy", "true");
  await expect(page.getByRole("status")).toContainText("正在创作新作品");
  await expect(page.getByRole("button", { name: "备选作品 2" })).toBeDisabled();

  await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();
  await expect(page.getByText("当前作品 1 / 3", { exact: true })).toBeVisible();
  await expect(page.locator("body")).not.toContainText(engineeringCopy);
  const visualBefore = await page.getByTestId("creation-main-visual").boundingBox();
  const prompt = page.getByRole("textbox", { name: "创作要求" });
  const revisedPrompt = "三瓶果汁靠近主视觉中央，使用柔和晨光，背景留出课堂提问空间。";
  await prompt.fill(revisedPrompt);
  await expect(page.getByRole("button", { name: "就用这张" })).toBeDisabled();

  await page.getByRole("button", { name: "按新要求再画一组" }).click();
  await expect(workspace).toHaveAttribute("aria-busy", "true");
  await expect(page.getByTestId("creation-main-visual")).toHaveAttribute(
    "data-render-generation",
    "1",
  );
  await expect(prompt).toBeDisabled();
  const visualDuring = await page.getByTestId("creation-main-visual").boundingBox();
  expect(visualBefore).not.toBeNull();
  expect(visualDuring).not.toBeNull();
  expect(Math.abs((visualBefore?.y ?? 0) - (visualDuring?.y ?? 0))).toBeLessThanOrEqual(2);
  expect(Math.abs((visualBefore?.height ?? 0) - (visualDuring?.height ?? 0))).toBeLessThanOrEqual(
    2,
  );

  await expect(page.getByRole("button", { name: "就用这张" })).toBeEnabled();
  await expect(page.getByTestId("creation-main-visual")).toHaveAttribute(
    "data-render-generation",
    "2",
  );
  await expect(workspace).toHaveAttribute("data-generation", "2");
  await expect(workspace).toHaveAttribute("aria-busy", "false");
  await page.reload();
  await expect(page.getByRole("textbox", { name: "创作要求" })).toHaveValue(revisedPrompt);
  await expect(page.getByRole("region", { name: "创作结果" })).toHaveAttribute(
    "data-generation",
    "2",
  );
});

test("图片结果可直接打开编辑图片并生成修改版", async ({ page }) => {
  await openReadyImageStudio(page);

  await page.getByRole("button", { name: "编辑图片" }).click();
  const dialog = page.getByRole("dialog", { name: "编辑这张图片" });
  await expect(dialog).toBeVisible();

  const editRequest = "保留三瓶果汁，把背景改得更干净，并拉开瓶子之间的距离。";
  await page.getByRole("textbox", { name: "图片修改要求" }).fill(editRequest);
  await page.getByRole("button", { name: "生成修改版" }).click();

  const workspace = page.getByRole("region", { name: "创作结果" });
  await expect(dialog).toBeHidden();
  await expect(workspace).toHaveAttribute("aria-busy", "true");
  await expect(page.getByRole("button", { name: "就用这张" })).toBeEnabled();
  await expect(page.getByRole("textbox", { name: "创作要求" })).toHaveValue(editRequest);
  await expect(workspace).toHaveAttribute("data-generation", "2");
});

test("1440×900 使用上方展示区和底部悬浮输入台", async ({ page }) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await openReadyImageStudio(page);

  const workspace = page.getByRole("region", { name: "创作工作区" });
  const previewPanel = page.getByTestId("creation-preview-panel");
  const mainVisual = page.getByTestId("creation-main-visual");
  const composerPanel = page.getByTestId("creation-composer-panel");
  const prompt = page.getByRole("textbox", { name: "创作要求" });
  const workspaceBox = await workspace.boundingBox();
  const previewBox = await previewPanel.boundingBox();
  const visualBox = await mainVisual.boundingBox();
  const composerBox = await composerPanel.boundingBox();
  const promptBox = await prompt.boundingBox();
  expect(workspaceBox).not.toBeNull();
  expect(previewBox).not.toBeNull();
  expect(composerBox).not.toBeNull();
  expect(promptBox?.width ?? 0).toBeGreaterThanOrEqual(700);
  expect(previewBox?.width ?? 0).toBeGreaterThanOrEqual(620);
  expect(previewBox?.width ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(760);
  expect(visualBox?.width ?? 0).toBeGreaterThanOrEqual(480);
  expect(visualBox?.width ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(720);
  expect(visualBox?.height ?? 0).toBeGreaterThanOrEqual(384);
  expect(visualBox?.height ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(576);
  expect((visualBox?.width ?? 0) / (visualBox?.height ?? 1)).toBeCloseTo(4 / 3, 2);
  expect(workspaceBox?.y ?? 0).toBeLessThan(composerBox?.y ?? 0);
  expect((workspaceBox?.y ?? 0) + (workspaceBox?.height ?? 0)).toBeLessThanOrEqual(
    (composerBox?.y ?? 0) + 1,
  );
  expect((composerBox?.y ?? 900) + (composerBox?.height ?? 0)).toBeLessThanOrEqual(900);

  for (const control of [
    prompt,
    page.getByRole("button", { name: "上传参考图" }),
    page.getByRole("combobox", { name: "图片比例" }),
    page.getByRole("button", { name: "编辑图片" }),
    page.getByRole("button", { name: "创作设置" }),
    page.getByRole("button", { name: "按新要求再画一组" }),
    page.getByRole("button", { name: "就用这张" }),
  ]) {
    await expect(control).toBeInViewport();
    const box = await control.boundingBox();
    expect((box?.y ?? 900) + (box?.height ?? 0)).toBeLessThanOrEqual(900);
  }
  await expect(page.getByRole("combobox", { name: "创作模型" })).toHaveCount(0);
  await page.getByRole("button", { name: "创作设置" }).click();
  await expect(page.getByLabel("创作模型")).toBeInViewport();
  await expect(page.getByLabel("比例", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "创作设置" }).click();
  await workspace.evaluate((element) => element.scrollTo({ top: element.scrollHeight }));
  await expect(page.getByRole("button", { name: "备选作品 1" })).toBeInViewport();
  await expectNoA11yViolations(page);
});

test("长提示词自动扩展输入台并保留主画布空间", async ({ page }) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await openReadyImageStudio(page);

  const prompt = page.getByRole("textbox", { name: "创作要求" });
  const composer = page.getByTestId("creation-composer-panel");
  const shortPromptBox = await prompt.boundingBox();
  await prompt.fill(
    Array.from(
      { length: 18 },
      (_, index) => `第 ${String(index + 1)} 项课堂画面要求：保留主体层次并明确学生观察重点。`,
    ).join("\n"),
  );
  const longPromptBox = await prompt.boundingBox();
  const composerBox = await composer.boundingBox();
  const promptMetrics = await prompt.evaluate((element) => ({
    clientHeight: element.clientHeight,
    overflowY: getComputedStyle(element).overflowY,
    scrollHeight: element.scrollHeight,
  }));

  expect(longPromptBox?.height ?? 0).toBeGreaterThan(shortPromptBox?.height ?? 0);
  expect(longPromptBox?.height ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(320);
  expect(promptMetrics.scrollHeight).toBeGreaterThan(promptMetrics.clientHeight);
  expect(promptMetrics.overflowY).toBe("auto");
  expect((composerBox?.y ?? 900) + (composerBox?.height ?? 0)).toBeLessThanOrEqual(900);
  await expect(page.getByRole("button", { name: "按新要求再画一组" })).toBeInViewport();
});

test("1280×800 首屏可查看结果并直接在底部调整", async ({ page }) => {
  await page.setViewportSize({ height: 800, width: 1280 });
  await openReadyImageStudio(page);

  for (const control of [
    page.getByRole("textbox", { name: "创作要求" }),
    page.getByRole("button", { name: "上传参考图" }),
    page.getByRole("combobox", { name: "图片比例" }),
    page.getByRole("button", { name: "编辑图片" }),
    page.getByRole("button", { name: "创作设置" }),
    page.getByRole("button", { name: "按新要求再画一组" }),
  ]) {
    await expect(control).toBeInViewport();
  }

  const dimensions = await page.evaluate(() => ({
    clientHeight: document.documentElement.clientHeight,
    clientWidth: document.documentElement.clientWidth,
    scrollHeight: document.documentElement.scrollHeight,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
  const visual = await page.getByTestId("creation-main-visual").boundingBox();
  expect(visual?.width ?? 0).toBeGreaterThanOrEqual(480);
  expect(visual?.width ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(720);
  await expect(page.getByRole("button", { name: "就用这张" })).toBeInViewport();
  const workArea = page.getByRole("region", { name: "创作工作区" });
  await workArea.evaluate((element) => element.scrollTo({ top: element.scrollHeight }));
  await expect(page.getByRole("button", { name: "备选作品 1" })).toBeInViewport();
});

test("等效 110% 缩放时视频创作台保持紧凑", async ({ page }) => {
  await page.setViewportSize({ height: 818, width: 1164 });
  await loginAsTeacher(page);
  await page.goto("/app/creation/videos");
  await page.getByRole("button", { name: "开始创作视频" }).click();
  await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();

  const visual = await page.getByTestId("creation-main-visual").boundingBox();
  const preview = await page.getByTestId("creation-preview-panel").boundingBox();
  expect(visual?.width ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(720);
  expect(preview?.width ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(900);
  await expect(page.getByRole("textbox", { name: "创作要求" })).toBeInViewport();
  await expect(page.getByRole("button", { name: "按新要求再做一组" })).toBeInViewport();
});

test("390px 下输入台固定可用并能按需展开画面细节", async ({ page }) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await openReadyImageStudio(page);
  const visualBox = await page.getByTestId("creation-main-visual").boundingBox();
  expect(visualBox?.y ?? 0).toBeGreaterThanOrEqual(128);
  expect(visualBox?.width ?? 0).toBeGreaterThanOrEqual(300);
  expect(visualBox?.height ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(360);
  const composerBox = await page.getByTestId("creation-composer-panel").boundingBox();
  expect((composerBox?.y ?? 844) + (composerBox?.height ?? 0)).toBeLessThanOrEqual(844);
  const prompt = page.getByRole("textbox", { name: "创作要求" });
  await expect(prompt).toBeInViewport();
  const promptHeight = await prompt.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }));
  expect(promptHeight.scrollHeight).toBeLessThanOrEqual(promptHeight.clientHeight);
  const settingsTrigger = page.getByRole("button", { name: "创作设置" });
  await expect(page.getByTestId("creation-composer-panel")).toContainText(
    "课堂插画 · 自动比例 · 纸艺微缩 · 3 张",
  );
  await settingsTrigger.click();
  await page.getByRole("button", { name: "画面细节" }).click();
  await expect(page.getByRole("complementary", { name: "画面细节调整" })).toBeVisible();
  await expect(page.getByLabel("画面安排")).toBeInViewport();
  await expect(page.getByLabel("画面安排")).toBeFocused();
  await expectNoA11yViolations(page);
  await page.getByRole("button", { name: "关闭画面细节" }).click();
  await expect(page.getByRole("textbox", { name: "创作要求" })).toBeVisible();
});

test("图片比例同步应用到预览并下载当前真实素材", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/images");
  await chooseSelect(page, "图片比例", "16:9");
  await page.getByRole("button", { name: "开始创作图片" }).click();
  await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();

  const visualRatio = await page.getByTestId("creation-main-visual").evaluate((element) => {
    const box = element.getBoundingClientRect();
    return box.width / box.height;
  });
  expect(visualRatio).toBeCloseTo(16 / 9, 2);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载这张图片" }).click();
  const download = await downloadPromise;
  const downloadPath = await download.path();
  if (!downloadPath) throw new Error("下载文件路径不可用");
  const content = await readFile(downloadPath);
  expect(download.suggestedFilename()).toMatch(/\.webp$/);
  expect(webpDimensions(content)).toEqual({ height: 900, width: 1600 });
  expect(content.byteLength).toBeGreaterThan(50_000);
});

test("创作结果可前后切换、放大并对比候选", async ({ page }) => {
  await openReadyImageStudio(page);

  await page.getByRole("button", { name: "下一张作品" }).click();
  await expect(page.getByRole("button", { name: "备选作品 2" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await page.getByRole("button", { name: "放大查看" }).click();
  await expect(page.getByRole("dialog", { name: "放大查看" })).toBeVisible();
  await expect(page.getByTestId("creation-enlarged-visual")).toBeVisible();
  await page.getByRole("button", { name: "关闭放大查看" }).click();

  await page.getByRole("button", { name: "对比作品" }).click();
  const comparison = page.getByRole("dialog", { name: "对比作品" });
  await expect(comparison).toBeVisible();
  await expect(comparison.getByRole("button", { name: /查看作品/ })).toHaveCount(3);
  await comparison.getByRole("button", { name: "关闭作品对比" }).click();
  await expect(page.getByRole("button", { name: "全屏查看" })).toBeVisible();
});

test("全屏预览退出后再打开保存对话框", async ({ page }) => {
  await openReadyImageStudio(page);
  await page.getByRole("button", { name: "就用这张" }).click();
  await page.getByRole("button", { name: "全屏查看" }).click();
  await expect.poll(() => page.evaluate(() => document.fullscreenElement !== null)).toBe(true);

  await page.getByRole("button", { name: "保存到项目" }).click();
  await expect.poll(() => page.evaluate(() => document.fullscreenElement === null)).toBe(true);
  await expect(page.getByRole("dialog", { name: "保存到项目" })).toBeInViewport();
});

test("独立创作首次选定项目后自动挂载后续作品并可查看项目资产", async ({ page }) => {
  await openReadyImageStudio(page);
  await page.getByRole("button", { name: "就用这张" }).click();
  await page.getByRole("button", { name: "保存到项目" }).click();
  const dialog = page.getByRole("dialog", { name: "保存到项目" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "保存到这个位置" }).click();
  await expect(page.getByText(/已挂载到“/)).toBeVisible();
  await page.getByRole("button", { name: "查看项目资产" }).click();
  await expect(page).toHaveURL(/\/app\/projects\/.*\/results$/);
  await expect(page.getByRole("heading", { name: "素材与成果" })).toBeVisible();

  await page.goBack();
  const prompt = page.getByRole("textbox", { name: "创作要求" });
  await prompt.fill("让三个标签之间留出更清晰的对比空间。");
  await page.getByRole("button", { name: "按新要求再画一组" }).click();
  await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();
  await page.getByRole("button", { name: "就用这张" }).click();
  await page.getByRole("button", { name: "保存到项目" }).click();
  await expect(page.getByRole("dialog", { name: "保存到项目" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "查看项目资产" })).toBeVisible();
});

test("PPT 候选会同步切换当前课件预览", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/presentations");
  await page.getByRole("button", { name: "开始制作 PPT" }).click();
  await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();

  const currentPreview = page
    .getByTestId("creation-main-visual")
    .locator('[role="img"] img')
    .last();
  const firstSource = await currentPreview.getAttribute("src");
  await page.getByRole("button", { name: "备选作品 2" }).click();
  await expect(currentPreview).not.toHaveAttribute("src", firstSource ?? "");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载课件预览" }).click();
  const download = await downloadPromise;
  const downloadPath = await download.path();
  if (!downloadPath) throw new Error("下载文件路径不可用");
  const content = await readFile(downloadPath, "utf8");
  expect(content.match(/<section>/g)).toHaveLength(5);
});
