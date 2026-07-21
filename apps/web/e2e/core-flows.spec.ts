import { expect, test } from "@playwright/test";
import { loginAsAdmin, loginAsTeacher } from "./support/auth";
import { unlockWorkbenchStep } from "./support/runtime";

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000101";

test("首页先进入真实项目，再由项目恢复课时工作台", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app");
  await expect(page.getByRole("heading", { level: 1, name: "认识百分数" })).toBeVisible();
  await page.getByRole("link", { name: "继续制作" }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}$`));
  await expect(page.getByRole("heading", { name: "认识百分数" }).first()).toBeVisible();
  await page.getByRole("link", { name: "打开教案" }).click();
  await expect(page).toHaveURL(
    new RegExp(`/projects/${projectId}/lessons/${lessonId}/work/lesson-plan`),
  );
  await expect(page.getByText("正在打开课堂作品")).toBeHidden({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "百分数的意义" }).first()).toBeVisible();
});

test("三类九套选择不阻塞教案", async ({ page }) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/intro-options`);
  await expect(page.getByText("正在打开课堂作品")).toBeHidden({ timeout: 15_000 });
  await expect(page.getByText("选择只决定课堂导入视频，不影响教案通过和 PPT 制作。")).toHaveCount(
    0,
  );
  const detailsPanel = page.getByTestId("intro-details-panel");
  await expect(detailsPanel.getByText("课堂从这个问题开始", { exact: true })).toBeVisible();
  for (const label of [
    "独立创意",
    "开场钩子",
    "最小课程回接",
    "课堂首问",
    "交接时刻",
    "视频不得提前讲授",
    "推荐理由",
  ]) {
    await expect(detailsPanel.getByText(label, { exact: true })).toHaveCount(0);
  }
  const optionCards = page.getByRole("button", { name: /方案：/ });
  await expect(optionCards).toHaveCount(9);
  const firstRow = await optionCards.evaluateAll((cards) =>
    cards.slice(0, 3).map((card) => Math.round(card.getBoundingClientRect().y)),
  );
  expect(new Set(firstRow).size).toBe(1);

  await page.setViewportSize({ height: 768, width: 1024 });
  await page.reload();
  await expect(optionCards.last()).toBeInViewport();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1024);

  await page.setViewportSize({ height: 844, width: 390 });
  await page.reload();
  const selectedSummary = page.getByTestId("intro-selected-summary");
  await expect(selectedSummary).toBeInViewport();
  await expect(page.getByText("查看开场与课堂回接", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "选择故事方案：失而复得的航海图" })).toBeVisible();
  await page.getByRole("button", { name: "选择故事方案：失而复得的航海图" }).click();
  await expect(selectedSummary).toContainText("失而复得的航海图");
  await page.getByRole("button", { name: "编写母版剧本", exact: true }).click();
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/intro-options`);
  await expect(selectedSummary).toContainText("当前采用");
  await expect(page.getByRole("button", { name: "当前采用方案" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "编写母版剧本", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "选择科普方案：会变色的百格窗" }).click();
  await expect(page.getByRole("button", { name: "编写母版剧本", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "返回当前方案" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: "编写母版剧本", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "选择故事方案：失而复得的航海图" }).click();
  await expect(selectedSummary).toContainText("当前采用");
  await expect(page.getByRole("button", { name: "当前采用方案" })).toHaveCount(0);
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan`);
  await expect(page.getByRole("button", { name: "确认教案" })).toBeVisible();
});

test("改用课堂导入方案后旧母版剧本需要按新方案更新", async ({ page }) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await loginAsTeacher(page);
  const introUrl = `/app/projects/${projectId}/lessons/${lessonId}/work/intro-options`;
  const scriptUrl = `/app/projects/${projectId}/lessons/${lessonId}/work/master-script`;

  await page.goto(introUrl);
  await page.getByRole("button", { name: "编写母版剧本", exact: true }).click();
  await page.goto(introUrl);
  const firstEditButton = page.getByRole("button", { name: "编辑方案" });
  await firstEditButton.click();
  const firstDrawer = page.getByRole("dialog", { name: "内容要求" });
  await firstDrawer
    .getByRole("textbox", { name: "你希望怎样调整" })
    .fill("增加一次学生观察标签的过程");
  await firstDrawer.getByRole("button", { name: "按新要求重新生成" }).click();
  await expect(firstDrawer.getByRole("status")).toContainText("新方案已生成");
  await firstDrawer.getByRole("button", { name: "查看新方案" }).click();
  await expect(firstEditButton).toBeFocused();
  await expect(page.getByRole("button", { name: "编写母版剧本", exact: true })).toBeEnabled();
  await page.setViewportSize({ height: 844, width: 390 });
  await page.reload();
  await expect(page.getByRole("button", { name: "返回当前方案" })).toBeVisible();
  await page.getByRole("button", { name: "返回当前方案" }).click();
  await expect(page.getByTestId("intro-selected-summary")).toContainText("当前采用");
  await expect(page.getByRole("button", { name: "返回当前方案" })).toHaveCount(0);
  await expect(page.getByText("增加一次学生观察标签的过程")).toHaveCount(0);
  await page.setViewportSize({ height: 900, width: 1440 });
  await page.goto(scriptUrl);
  await expect(page.getByRole("heading", { name: "果汁标签侦探" }).first()).toBeVisible();
  await expect(page.getByText("增加一次学生观察标签的过程")).toHaveCount(0);
  await page.getByRole("button", { name: "确认母版剧本" }).click();

  await page.goto(introUrl);
  await page.getByRole("button", { name: "选择科普方案：会变色的百格窗" }).click();
  const editButton = page.getByRole("button", { name: "编辑方案" });
  await editButton.click();
  const drawer = page.getByRole("dialog", { name: "内容要求" });
  await expect(drawer).toBeVisible();
  await expect(drawer).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(editButton).toBeFocused();
  await editButton.click();
  await expect(drawer).toBeVisible();
  const drawerBox = await drawer.boundingBox();
  expect(drawerBox?.width ?? 0).toBeGreaterThanOrEqual(380);
  expect(drawerBox?.width ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(420);
  await expect(drawer.getByText("平台锁定约束")).toHaveCount(0);
  await expect(drawer.getByText(/账号|密钥|结构校验/)).toHaveCount(0);
  await drawer
    .getByRole("textbox", { name: "你希望怎样调整" })
    .fill("增加学生观察百格窗变化的过程，减少旁白");
  await drawer.getByRole("button", { name: "按新要求重新生成" }).click();
  await expect(drawer.getByRole("status")).toContainText("正在按新要求准备方案");
  await expect(drawer.getByRole("status")).toContainText("新方案已生成");
  await drawer.getByRole("button", { name: "查看新方案" }).click();
  await expect(editButton).toBeFocused();
  await expect(
    page.getByText(/新版本重点强化“增加学生观察百格窗变化的过程，减少旁白”/).last(),
  ).toBeVisible();
  await expect(page.getByText(/先请学生说出观察，再直接提问/).last()).toBeVisible();
  await expect(page.getByText(/先说说你观察到了什么/).last()).toBeVisible();
  await page.getByRole("button", { name: "编写母版剧本", exact: true }).click();
  await expect(page).toHaveURL(scriptUrl);
  await expect(page.getByRole("heading", { name: "果汁标签侦探" }).first()).toBeVisible();
  await expect(page.getByText(/课堂导入已经改用“会变色的百格窗”/)).toBeVisible();
  await expect(page.getByRole("button", { name: "根据新方案更新剧本" })).toBeVisible();
  await page.getByRole("button", { name: "根据新方案更新剧本" }).click();
  await expect(page.getByRole("heading", { name: "会变色的百格窗" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "确认母版剧本" })).toBeVisible();
  await expect(
    page
      .getByTestId("markdown-preview")
      .getByText("镜头定格在 37 格亮起的完整百格窗。 画面停住，不再补充旁白，把判断留给学生。", {
        exact: true,
      }),
  ).toBeVisible();
  await expect(page.getByText(/三张标签并排出现/)).toHaveCount(0);
  await expect(
    page.getByText(/新版本重点强化“增加学生观察百格窗变化的过程，减少旁白”/).last(),
  ).toBeVisible();
});

test("PPT 正文按可用高度完整显示", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 800, width: 1280 });
  await loginAsTeacher(page);
  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-pages");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-pages`);

  await expect(page.getByRole("button", { name: "查看检查结果" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "查看参考内容" })).toBeVisible();
  await expect(page.getByRole("button", { name: "编辑内容要求" })).toBeVisible();
  const slideImage = page.locator('[role="img"] img');
  await expect(slideImage).toHaveAttribute("src", /ppt-content-hundred-grid/);
  await page.getByRole("button", { name: "重新生成本页" }).click();
  await expect(page.getByRole("status")).toContainText("已重新生成并保存");
  await expect(page.getByTestId("ppt-regenerated-note")).toBeVisible();

  const stageBox = await page.getByTestId("ppt-canvas-stage").boundingBox();
  const slideBox = await page.getByTestId("ppt-slide-frame").boundingBox();
  expect(stageBox).not.toBeNull();
  expect(slideBox).not.toBeNull();
  expect(slideBox?.width ?? 0).toBeGreaterThan(600);
  expect(slideBox?.height ?? 0).toBeGreaterThan(320);
  expect((slideBox?.y ?? 0) + (slideBox?.height ?? 0)).toBeLessThanOrEqual(
    (stageBox?.y ?? 0) + (stageBox?.height ?? 0) + 1,
  );
  expect((stageBox?.y ?? 0) + (stageBox?.height ?? 0)).toBeLessThanOrEqual(800);
  await page.screenshot({
    animations: "disabled",
    path: testInfo.outputPath("ppt-pages-1280.png"),
  });

  await page.setViewportSize({ height: 768, width: 1024 });
  await page.reload();
  const mediumStageBox = await page.getByTestId("ppt-canvas-stage").boundingBox();
  const mediumSlideBox = await page.getByTestId("ppt-slide-frame").boundingBox();
  expect(mediumStageBox).not.toBeNull();
  expect(mediumSlideBox).not.toBeNull();
  expect((mediumSlideBox?.width ?? 0) / (mediumSlideBox?.height ?? 1)).toBeCloseTo(16 / 9, 2);
  const mediumTopGap = (mediumSlideBox?.y ?? 0) - (mediumStageBox?.y ?? 0);
  const mediumBottomGap =
    (mediumStageBox?.y ?? 0) +
    (mediumStageBox?.height ?? 0) -
    ((mediumSlideBox?.y ?? 0) + (mediumSlideBox?.height ?? 0));
  expect(Math.abs(mediumTopGap - mediumBottomGap)).toBeLessThanOrEqual(2);

  await page.setViewportSize({ height: 844, width: 390 });
  await page.reload();
  const mobileStageBox = await page.getByTestId("ppt-canvas-stage").boundingBox();
  const mobileSlideBox = await page.getByTestId("ppt-slide-frame").boundingBox();
  expect(mobileStageBox).not.toBeNull();
  expect(mobileSlideBox).not.toBeNull();
  expect((mobileSlideBox?.width ?? 0) / (mobileSlideBox?.height ?? 1)).toBeCloseTo(16 / 9, 2);
  expect(mobileStageBox?.height ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(
    (mobileSlideBox?.height ?? 0) + 24,
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("独立创作按创作、选用、保存顺序推进", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/images");
  await page.getByRole("button", { name: "开始创作图片" }).click();
  await expect(page.getByRole("status")).toContainText("正在创作新作品");
  await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();
  await expect(page.getByText("当前作品 1 / 3", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "就用这张" }).click();
  await expect(page.getByRole("button", { name: "保存到项目" })).toBeVisible();
  await page.getByRole("button", { name: "保存到项目" }).click();
  await expect(page.getByRole("dialog", { name: "保存到项目" })).toBeVisible();
});

test("管理端内容包按检查流程发布", async ({ page }) => {
  await loginAsAdmin(page);
  await page.goto("/admin/content");
  await page.getByRole("button", { name: "导入内容包" }).click();
  await expect(page.getByText("标准导入流程")).toBeVisible();
  await page.getByLabel("选择内容包文件").setInputFiles({
    name: "shanhai-content-小学数学教案结构-v2.zip",
    mimeType: "application/zip",
    buffer: Buffer.from("content-package"),
  });
  await expect(page.getByText("ZIP 文件名元数据符合规则；未读取压缩包内容。")).toBeVisible();
  await page.getByRole("button", { name: "继续" }).click();
  await expect(page.getByLabel("选择内容包文件")).toHaveCount(0);
  await expect(page.getByText("ZIP 文件名元数据符合规则；未读取压缩包内容。")).toBeVisible();
  await page.getByRole("button", { name: "继续" }).click();
  await expect(page.getByText("将发布“小学数学教案结构”归档版本 v2")).toBeVisible();
  await page.getByRole("button", { name: "继续" }).click();
  await expect(page.getByText("试运行通过")).toBeVisible();
  await page.getByRole("button", { name: "发布新版本" }).click();
  await expect(page.getByText("新版本已发布并加入内容列表")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("cell", { name: "小学数学教案结构" })).toBeVisible();
});

test("全局搜索与通知可以打开并跳转", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app");
  await page.getByRole("button", { name: "搜索" }).click();
  await page.getByRole("textbox", { name: "搜索项目、课时和功能" }).fill("创作");
  await page.getByRole("link", { name: "图片创作台" }).click();
  await expect(page).toHaveURL(/\/app\/creation\/images$/);
  await page.goto("/app");
  await page.getByRole("button", { name: /通知/ }).click();
  await expect(page.getByText("教案已完成检查")).toBeVisible();
});

test("手机端可以从流程抽屉切换步骤", async ({ page }) => {
  await loginAsTeacher(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan`);
  const workbenchHeader = page.locator('[data-testid="project-workbench"] > header');
  await expect(workbenchHeader).toContainText("认识百分数");
  await expect(workbenchHeader).toContainText("第 1 课时");
  await expect(workbenchHeader).toContainText("编写并确认教案");
  await expect(page.getByRole("button", { name: "打开课时流程" })).toContainText("流程");
  await expect(page.getByRole("link", { name: /项需要你处理 · 查看任务/ })).toBeVisible();
  await page.getByRole("button", { name: "打开课时流程" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("dialog").getByRole("link", { name: "安排页面" }).click();
  await expect(page).toHaveURL(/\/work\/ppt-outline$/);
});

test("受控弹窗关闭后焦点回到触发按钮", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/images");
  await page.getByRole("button", { name: "开始创作图片" }).click();
  await page.getByRole("button", { name: "就用这张" }).click();
  const saveTrigger = page.getByRole("button", { name: "保存到项目" });
  await saveTrigger.click();
  await expect(page.getByRole("dialog", { name: "保存到项目" })).toBeVisible();
  await page.getByRole("button", { name: "关闭" }).click();
  await expect(saveTrigger).toBeFocused();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan`);
  const flowTrigger = page.getByRole("button", { name: "打开课时流程" });
  await flowTrigger.click();
  await expect(page.getByRole("dialog", { name: "课时制作流程" })).toBeVisible();
  await page.getByRole("button", { name: "关闭课时流程" }).click();
  await expect(flowTrigger).toBeFocused();
});

test("1024×768 打开模型配置后保存操作可达", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await loginAsAdmin(page);
  await page.goto("/admin/models");
  await page.getByRole("button", { name: "配置" }).first().click();
  await expect(page.getByRole("heading", { name: "正在配置：文本生成" })).toBeFocused();
  await expect(page.getByRole("button", { name: "保存配置" })).toBeInViewport();
});

test("课时和 PPT 页面排序支持键盘移动", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/materials`);
  await page.getByRole("button", { name: "重新编辑课时" }).click();
  const lessonHandle = page.getByRole("button", { name: /拖动第 1 课时/ }).first();
  await lessonHandle.press("ArrowDown");
  await expect(page.locator('input[aria-label="课时名称"]').first()).toHaveValue(
    "第 2 课时 · 百分数与分数、小数",
  );
  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-outline");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-outline`);
  await page.getByRole("button", { name: /拖动第 2 页/ }).press("ArrowDown");
  await expect(page.locator('input[aria-label="第 2 页标题"]')).toHaveValue("百格图里的 37%");
});

test("空项目、部分成功和过期内容提供明确处理入口", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}?scenario=project_empty`);
  await expect(page.getByRole("heading", { name: "先上传当前知识点的教材" })).toBeVisible();
  await page.goto(
    `/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan?scenario=node_partial`,
  );
  await expect(page.getByRole("button", { name: "重新处理未完成内容" })).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/后台任务|局部重试|上游内容|候选/);
  await page.goto(
    `/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan?scenario=node_stale`,
  );
  await expect(page.getByRole("button", { name: "根据新内容更新" })).toBeVisible();
  await expect(page.getByRole("button", { name: "继续使用当前版本" })).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/后台任务|局部重试|上游内容|候选/);
  await page.goto(
    `/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan?scenario=node_running`,
  );
  await expect(page.getByRole("button", { name: "查看处理进度" })).toBeVisible();
});

test("保存冲突显示替换和另存为选择", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/batches/mock-batch");
  await page.getByRole("button", { name: "就用这张" }).click();
  await page.getByRole("button", { name: "保存到项目" }).click();
  await page.getByRole("button", { name: "保存到这个位置" }).click();
  await expect(page.getByText("作品已经保存，可在目标项目的素材与成果中查看。")).toBeVisible();
  await page.getByRole("button", { name: /观察标签的.*学生/ }).click();
  await page.getByRole("button", { name: "保存到项目" }).click();
  await page.getByRole("button", { name: "保存到这个位置" }).click();
  await expect(page.getByText("该位置已有当前作品")).toBeVisible();
  await expect(page.getByLabel("另存为项目通用素材")).toBeVisible();
});

test("任务中心可以恢复实时更新并重新处理未完成内容", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/tasks");
  await page.getByRole("button", { name: "恢复更新" }).click();
  await expect(page.getByText("进度实时更新中")).toBeVisible();
  await page.getByRole("button", { name: "等待处理" }).click();
  await page.getByRole("button", { name: "重新处理未完成内容" }).click();
  await expect(page.getByText("失败图片已开始重新处理")).toBeVisible();
});
