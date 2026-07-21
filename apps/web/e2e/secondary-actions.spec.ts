import { expect, test, type Page } from "@playwright/test";
import { loginAsTeacher } from "./support/auth";
import { unlockWorkbenchStep } from "./support/runtime";

async function chooseSelect(page: Page, label: string, option: string) {
  const combobox = page.getByRole("combobox", { name: label });
  if (!(await combobox.isVisible())) {
    await page.getByRole("button", { name: "创作设置" }).click();
  }
  await combobox.click();
  await page.getByRole("option", { name: option }).click();
}

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000101";
const workUrl = `/app/projects/${projectId}/lessons/${lessonId}/work`;

test("创作设置、参考图和创作要求刷新后保留", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/images");
  await page.getByLabel("画面内容").fill("三瓶果汁摆在木桌上，保留清晰前后层次和课堂观察空间。");
  await chooseSelect(page, "画面风格", "清透插画");
  await page.getByTestId("reference-image-input").setInputFiles({
    name: "果汁参考图.png",
    mimeType: "image/png",
    buffer: Buffer.from("image-reference"),
  });
  await page.getByRole("button", { name: "画面细节" }).click();
  await page.getByLabel("画面安排").fill("主体居中，前景保留一块课堂提问空间。");
  await page.getByRole("button", { name: "关闭画面细节" }).click();
  await page.getByRole("button", { name: "创作设置" }).click();
  await page.getByRole("button", { name: "完整要求" }).click();
  await page.getByLabel("你想要的作品").fill("使用真实课堂光线，三瓶果汁标签不出现准确文字。");
  await page.getByRole("button", { name: "保存创作要求" }).click();
  await page.reload();
  await expect(page.getByLabel("画面内容")).toHaveValue(
    "使用真实课堂光线，三瓶果汁标签不出现准确文字。",
  );
  await page.getByRole("button", { name: "创作设置" }).click();
  await expect(page.getByRole("combobox", { name: "画面风格" })).toContainText("清透插画");
  await expect(page.getByTestId("creation-parameter-bar")).toContainText("果汁参考图.png");
  await page.getByRole("button", { name: "画面细节" }).click();
  await expect(page.getByLabel("画面安排")).toHaveValue("主体居中，前景保留一块课堂提问空间。");
  await page.getByRole("button", { name: "关闭画面细节" }).click();
  await page.getByRole("button", { name: "开始创作图片" }).click();
  await page.reload();
  await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();
});

test("母版剧本增加场次并刷新后保留", async ({ page }) => {
  await loginAsTeacher(page);
  await unlockWorkbenchStep(page, projectId, lessonId, "master-script");
  await page.goto(`${workUrl}/master-script`);
  await expect(page.getByRole("button", { name: "导入方案" })).toBeVisible();
  await expect(page.getByText("课堂交接：", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "增加场次" }).click();
  await page.getByRole("button", { name: "编辑" }).click();
  const script = page.getByRole("textbox", { name: "母版剧本正文" });
  await expect(script).toHaveValue(/## 场次 4｜新增场次/);
  await script.fill((await script.inputValue()).replace("新增场次", "回到课堂"));
  await page.getByRole("button", { name: "保存修改" }).click();
  await page.reload();
  await expect(page.getByTestId("markdown-preview")).toContainText("场次 4｜回到课堂");
  await page.getByRole("button", { name: "确认母版剧本" }).click();
  await expect(page.getByRole("button", { name: "编辑", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "重新编辑剧本" }).click();
  await expect(page.getByRole("button", { name: "增加场次" })).toBeVisible();
  await expect(page.getByRole("button", { name: "编辑", exact: true })).toBeEnabled();
});

test("封面重新生成和下载预览均有结果", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 900, width: 1280 });
  await loginAsTeacher(page);
  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-cover");
  await page.goto(`${workUrl}/ppt-cover`);
  await page.getByRole("button", { name: "重新生成" }).click();
  await expect(page.getByText("已生成并切换到新的备选封面")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载预览" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.svg$/);
  await page.getByRole("button", { name: "采用这张封面" }).click();
  await expect(page.getByRole("button", { name: "选择百格光窗" })).toBeDisabled();
  await expect(page.getByRole("link", { name: "制作 PPT 正文" })).toBeVisible();
  await page.screenshot({
    animations: "disabled",
    path: testInfo.outputPath("ppt-cover-horizontal-candidates-1280.png"),
  });
  await page.getByRole("button", { name: "重新选择封面" }).click();
  await expect(page.getByRole("button", { name: "选择百格光窗" })).toBeEnabled();
});

test("资产检查和视频生成进入任务中心", async ({ page }) => {
  await loginAsTeacher(page);
  await unlockWorkbenchStep(page, projectId, lessonId, "video-assets");
  await page.goto(`${workUrl}/video-assets`);
  await page.getByRole("button", { name: "重新检查资产清单" }).click();
  await expect(page.getByText("资产清单已重新检查")).toBeVisible();
  await expect(page.getByRole("button", { name: "检查待生成内容" })).toHaveCount(0);
  await unlockWorkbenchStep(page, projectId, lessonId, "final-video");
  await page.goto(`${workUrl}/final-video`);
  await page.getByRole("button", { name: "开始生成视频" }).click();
  await expect(page.getByText("视频生成已开始，可在处理进度中查看")).toBeVisible();
  await page.goto("/app/tasks");
  await expect(page.getByText("课堂导入视频生成")).toBeVisible();
});

test("关键帧参考和单个关键帧重做状态刷新后保留", async ({ page }) => {
  await loginAsTeacher(page);
  await unlockWorkbenchStep(page, projectId, lessonId, "fine-storyboard");
  await page.goto(`${workUrl}/fine-storyboard`);
  const candidate = page.getByRole("button", { name: "关键帧参考 2" });
  await candidate.click();
  await page.getByRole("button", { name: "只重做这个关键帧" }).click();
  await expect(page.getByText("镜头 2 的关键帧示意已更新，其他镜头保持不变。")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: "关键帧参考 2" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
