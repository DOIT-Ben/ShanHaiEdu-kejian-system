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
  await page.getByRole("combobox", { name: label }).click();
  await page.getByRole("option", { name: option }).click();
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

test("新老师可按首页引导进入并用课堂建议补全要求", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation");
  await expect(page.locator("body")).not.toContainText(engineeringCopy);
  await expect(page.getByText("第一次使用？建议先画一张教学图片")).toBeVisible();
  await page.getByRole("link", { name: "去画一张" }).click();
  await expect(page.getByText("正在打开课堂作品")).toBeHidden({ timeout: 15_000 });
  await expect(page.getByText("先从这一步开始 · 画一张教学图片", { exact: true })).toBeVisible({
    timeout: 30_000,
  });

  const description = page.getByLabel("画面内容");
  await chooseSelect(page, "创作模型", "细节增强");
  await page.getByRole("button", { name: "留出板书区" }).click();
  await page.getByRole("button", { name: "留出板书区" }).click();
  const value = await description.inputValue();
  expect(value.match(/画面右侧留出干净的提问或板书空间。/g)).toHaveLength(1);
  await page.reload();
  await expect(page.getByLabel("画面内容")).toHaveValue(value);
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
    const outputBox = await page.getByTestId("creation-output-region").boundingBox();
    const composerBox = await page.getByTestId("creation-composer-panel").boundingBox();
    expect(outputBox).not.toBeNull();
    expect(composerBox).not.toBeNull();
    expect(composerBox?.y ?? 0).toBeGreaterThan(outputBox?.y ?? 0);
    await expect(page.getByRole("textbox", { name: studio.input })).toBeInViewport();
    await expect(page.getByLabel("创作模型")).toBeInViewport();
    await expect(page.getByLabel("比例")).toBeInViewport();
  }
});

test("图片结果可修改创作要求并经过稳定运行态重新创作", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/images");
  await page.getByRole("button", { name: "开始创作图片" }).click();

  const workspace = page.getByRole("region", { name: "创作结果" });
  await expect(workspace).toHaveAttribute("aria-busy", "true");
  await expect(page.getByRole("status")).toContainText("正在创作新作品");
  await expect(page.locator("header").getByText("正在创作", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "备选作品 2" })).toBeDisabled();

  await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();
  await expect(page.getByText("作品已完成", { exact: true })).toBeVisible();
  await expect(page.locator("body")).not.toContainText(engineeringCopy);
  await expect(page.getByText(/满意就选用；还想调整/)).toBeVisible();
  const visualBefore = await page.getByTestId("creation-main-visual").boundingBox();
  const prompt = page.getByRole("textbox", { name: "创作要求" });
  await page.getByRole("button", { name: "留出板书区" }).click();
  await expect(prompt).toHaveValue(/画面右侧留出干净的提问或板书空间/);
  const revisedPrompt = "三瓶果汁靠近主视觉中央，使用柔和晨光，背景留出课堂提问空间。";
  await prompt.fill(revisedPrompt);
  await expect(page.getByText("有修改，重新创作后生效")).toBeVisible();
  await expect(page.getByText(/下方要求已有修改/)).toBeVisible();
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

  await expect(page.getByText("第 2 轮作品已完成")).toBeVisible();
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

test("1440×900 使用上方展示区和底部悬浮输入台", async ({ page }) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await openReadyImageStudio(page);

  const outputRegion = page.getByTestId("creation-output-region");
  const previewPanel = page.getByTestId("creation-preview-panel");
  const mainVisual = page.getByTestId("creation-main-visual");
  const composerPanel = page.getByTestId("creation-composer-panel");
  const prompt = page.getByRole("textbox", { name: "创作要求" });
  const outputBox = await outputRegion.boundingBox();
  const previewBox = await previewPanel.boundingBox();
  const visualBox = await mainVisual.boundingBox();
  const composerBox = await composerPanel.boundingBox();
  const promptBox = await prompt.boundingBox();
  expect(outputBox).not.toBeNull();
  expect(previewBox).not.toBeNull();
  expect(composerBox).not.toBeNull();
  expect(promptBox?.width ?? 0).toBeGreaterThanOrEqual(700);
  expect(previewBox?.width ?? 0).toBeGreaterThanOrEqual(620);
  expect(previewBox?.width ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(760);
  expect(visualBox?.height ?? 0).toBeGreaterThanOrEqual(180);
  expect(visualBox?.height ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(260);
  expect((visualBox?.width ?? 0) / (visualBox?.height ?? 1)).toBeCloseTo(1, 2);
  expect(promptBox?.y ?? 0).toBeGreaterThan((visualBox?.y ?? 0) + (visualBox?.height ?? 0));
  expect(composerBox?.y ?? 0).toBeGreaterThanOrEqual(
    (outputBox?.y ?? 0) + (outputBox?.height ?? 0) - 1,
  );
  expect((composerBox?.y ?? 900) + (composerBox?.height ?? 0)).toBeLessThanOrEqual(900);

  for (const control of [
    page.getByRole("button", { name: "备选作品 1" }),
    page.getByRole("button", { name: "备选作品 2" }),
    page.getByRole("button", { name: "备选作品 3" }),
    prompt,
    page.getByLabel("创作模型"),
    page.getByLabel("比例"),
    page.getByRole("button", { name: "按新要求再画一组" }),
    page.getByRole("button", { name: "就用这张" }),
  ]) {
    await expect(control).toBeInViewport();
    const box = await control.boundingBox();
    expect((box?.y ?? 900) + (box?.height ?? 0)).toBeLessThanOrEqual(900);
  }
  await expectNoA11yViolations(page);
});

test("1280×800 首屏可查看结果并直接在底部调整", async ({ page }) => {
  await page.setViewportSize({ height: 800, width: 1280 });
  await openReadyImageStudio(page);

  for (const control of [
    page.getByRole("button", { name: "备选作品 1" }),
    page.getByRole("button", { name: "备选作品 2" }),
    page.getByRole("button", { name: "备选作品 3" }),
    page.getByRole("textbox", { name: "创作要求" }),
    page.getByLabel("创作模型"),
    page.getByLabel("比例"),
    page.getByRole("button", { name: "按新要求再画一组" }),
    page.getByRole("button", { name: "就用这张" }),
  ]) {
    await expect(control).toBeInViewport();
  }

  const dimensions = await page.evaluate(() => ({
    clientHeight: document.documentElement.clientHeight,
    clientWidth: document.documentElement.clientWidth,
    scrollHeight: document.documentElement.scrollHeight,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollHeight).toBeLessThanOrEqual(dimensions.clientHeight + 1);
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
});

test("390px 下输入台固定可用并能展开画面细节", async ({ page }) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await openReadyImageStudio(page);
  const visualBox = await page.getByTestId("creation-main-visual").boundingBox();
  expect(visualBox?.y ?? 0).toBeGreaterThanOrEqual(128);
  expect(visualBox?.height ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(280);
  const composerBox = await page.getByTestId("creation-composer-panel").boundingBox();
  expect((composerBox?.y ?? 844) + (composerBox?.height ?? 0)).toBeLessThanOrEqual(844);
  const prompt = page.getByRole("textbox", { name: "创作要求" });
  await expect(prompt).toBeInViewport();
  const promptHeight = await prompt.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }));
  expect(promptHeight.scrollHeight).toBeLessThanOrEqual(promptHeight.clientHeight);
  await page.getByRole("button", { name: "调整模型、比例和画面细节" }).click();
  await page.getByRole("button", { name: "画面细节" }).click();
  await expect(page.getByRole("complementary", { name: "画面细节调整" })).toBeVisible();
  await expect(page.getByLabel("画面安排")).toBeInViewport();
  await expect(page.getByLabel("画面安排")).toBeFocused();
  await expectNoA11yViolations(page);
  await page.getByRole("button", { name: "关闭画面细节" }).click();
  await expect(page.getByRole("textbox", { name: "创作要求" })).toBeVisible();
});

test("图片比例同步应用到预览和下载文件", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/images");
  await chooseSelect(page, "比例", "16:9");
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
  const content = await readFile(downloadPath, "utf8");
  expect(content).toContain('width="1600" height="900"');
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
