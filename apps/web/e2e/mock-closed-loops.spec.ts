import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { loginAsTeacher } from "./support/auth";
import { unlockWorkbenchStep } from "./support/runtime";

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000101";

test("未登录访问管理端时返回登录页", async ({ page }) => {
  await page.goto("/admin/content");
  await expect(page).toHaveURL(/\/login$/);
});

test("教师账号不能进入管理端", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/admin/content");
  await expect(page).toHaveURL(/\/app$/);
});

test("教材文件随新建项目进入教材页", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/projects/new");
  await page.getByLabel("项目名称").fill("百分数综合练习");
  await page.getByLabel("知识点").fill("百分数的综合应用");
  await page.locator('input[type="file"]').setInputFiles({
    name: "百分数综合练习.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 mock textbook"),
  });
  await page.getByRole("button", { name: "创建项目并检查教材" }).click();
  await expect(page).toHaveURL(/\/app\/projects\/[^/]+\/materials$/);
  await expect(page.getByRole("heading", { name: "教材与课时" })).toBeVisible();
  await expect(page.getByText("百分数综合练习.pdf")).toBeVisible();
  const approveLessons = page.getByRole("button", { name: "批准课时安排" });
  await expect(approveLessons).toBeEnabled({ timeout: 2_000 });
  await approveLessons.click();
  await expect(page.getByRole("button", { name: "重新编辑课时" })).toBeVisible();
  await page.getByRole("link", { name: "开始第 1 课时教案" }).click();
  await expect(page.getByTestId("markdown-preview")).toContainText("百分数的综合应用");
  await expect(page.getByTestId("markdown-preview")).not.toContainText("百分数表示");
});

test("新项目可以只通过页面操作走到真实视频生成门槛", async ({ page }, testInfo) => {
  test.setTimeout(60_000);
  await loginAsTeacher(page);
  await page.goto("/app/projects/new");
  await page.getByLabel("项目名称").fill("百分数视频课例");
  await page.getByLabel("知识点").fill("百分数的综合应用");
  await page.locator('input[type="file"]').setInputFiles({
    name: "百分数视频课例.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 mock textbook"),
  });
  await page.getByRole("button", { name: "创建项目并检查教材" }).click();
  await expect(page).toHaveURL(/\/app\/projects\/[^/]+\/materials$/);
  const projectId = page.url().match(/\/projects\/([^/]+)\/materials/)?.[1];
  if (!projectId) throw new Error("未取得新项目 ID");
  await expect(page.getByRole("button", { name: "批准课时安排" })).toBeEnabled({ timeout: 30_000 });
  await page.getByRole("button", { name: "批准课时安排" }).click();
  const lessonLink = page.getByRole("link", { name: "开始第 1 课时教案" });
  await expect(lessonLink).toBeVisible();
  const lessonId = (await lessonLink.getAttribute("href"))?.match(/lessons\/([^/]+)\/work/)?.[1];
  if (!lessonId) throw new Error("未取得新课时 ID");
  await lessonLink.click();
  await page.getByRole("button", { name: "确认教案" }).click();

  const workUrl = `/app/projects/${projectId}/lessons/${lessonId}/work`;
  await page.goto(`${workUrl}/intro-options`);
  await page
    .getByRole("button", { name: /选择.*方案/ })
    .first()
    .click();
  await page.getByRole("button", { name: "采用这套方案" }).click();
  await page.goto(`${workUrl}/master-script`);
  await page.getByRole("button", { name: "确认母版剧本" }).click();
  await page.goto(`${workUrl}/rough-storyboard`);
  await page.getByRole("button", { name: "确认故事镜头" }).click();
  await page.goto(`${workUrl}/video-style`);
  await page.getByRole("button", { name: "采用这个画面风格" }).click();
  await page.goto(`${workUrl}/video-assets`);
  await page.getByRole("link", { name: "去图片创作台" }).click();

  const assetCards = page.locator("aside").first().getByRole("button");
  await expect(assetCards).toHaveCount(4);
  for (let index = 0; index < 4; index += 1) {
    await assetCards.nth(index).click();
    const retry = page.getByRole("button", { name: "重新制作这张" });
    if (await retry.isVisible()) await retry.click();
    const adoptAsset = page.getByRole("button", { name: "就用这张" });
    if (await adoptAsset.isVisible()) await adoptAsset.click();
    await page.getByRole("button", { name: "保存到项目" }).click();
    await page
      .getByRole("dialog", { name: "保存到项目" })
      .getByRole("button", { name: "保存到这个位置" })
      .click();
    await expect(page.getByText("已保存到项目", { exact: true })).toBeVisible();
  }

  await page.goto(`${workUrl}/video-assets`);
  await page.getByTestId("workbench-content").getByRole("link", { name: "选择关键帧参考" }).click();
  const shotCards = page.getByRole("button", { name: /^镜头 \d/ });
  const fineDraftKey = `project:${projectId}:lesson:${lessonId}:fine-storyboard`;
  await expect(shotCards).toHaveCount(3);
  for (let index = 0; index < 3; index += 1) {
    const shotCard = shotCards.nth(index);
    await shotCard.click();
    await expect(shotCard).toHaveAttribute("aria-pressed", "true");
    let adopt = page.getByRole("button", { name: "选择这个关键帧参考" });
    if (!(await adopt.isVisible())) {
      const retry = page.getByRole("button", { name: "只重做这个关键帧" });
      if (await retry.isVisible()) {
        await retry.click();
        await expect(page.getByRole("button", { name: "选择这个关键帧参考" })).toBeVisible();
        adopt = page.getByRole("button", { name: "选择这个关键帧参考" });
      }
      const reselect = page.getByRole("button", { name: /重新选择.*关键帧/ });
      if (!(await adopt.isVisible()) && (await reselect.isVisible())) {
        await reselect.click();
        await expect(page.getByRole("button", { name: "选择这个关键帧参考" })).toBeVisible();
        adopt = page.getByRole("button", { name: "选择这个关键帧参考" });
      }
    }
    if (await adopt.isVisible()) {
      if (await adopt.isDisabled()) {
        await page.getByRole("button", { name: "只重做这个关键帧" }).click();
      }
      await expect(adopt).toBeEnabled();
      await adopt.click();
      await expect
        .poll(() =>
          page.evaluate((key) => {
            const raw = localStorage.getItem("shanhaiedu.mock-runtime.v1");
            if (!raw) return 0;
            const runtime = JSON.parse(raw) as {
              drafts?: Record<string, { value?: { adoptedShots?: string[] } }>;
            };
            return runtime.drafts?.[key]?.value?.adoptedShots?.length ?? 0;
          }, fineDraftKey),
        )
        .toBe(index + 1);
    }
  }
  await expect
    .poll(() =>
      page.evaluate((key) => {
        const raw = localStorage.getItem("shanhaiedu.mock-runtime.v1");
        if (!raw) return "missing";
        const runtime = JSON.parse(raw) as {
          nodeStates?: Record<string, { status?: string }>;
          drafts?: Record<string, { value?: { adoptedShots?: string[] } }>;
        };
        const draft = runtime.drafts?.[key];
        const node = Object.entries(runtime.nodeStates ?? {}).find(([nodeKey]) =>
          nodeKey.endsWith(":fine-storyboard"),
        );
        return `${String(draft?.value?.adoptedShots?.length ?? 0)}:${node?.[1]?.status ?? "missing"}`;
      }, fineDraftKey),
    )
    .toBe("3:approved");
  await expect(page.getByRole("link", { name: "查看视频生成状态" }).last()).toBeVisible();
  await page.getByRole("link", { name: "查看视频生成状态" }).last().click();
  await page.getByRole("button", { name: "开始生成视频" }).click();
  await expect(page.getByRole("button", { name: "视频尚未生成" })).toBeDisabled({
    timeout: 10_000,
  });
  await expect(page.getByText(/关键帧示意/).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "确认视频" })).toHaveCount(0);
  const flowNavigation = page.getByRole("navigation", { name: "课时制作流程" });
  await expect(
    flowNavigation.getByRole("link", { name: /生成课堂导入视频.*当前/ }),
  ).toBeInViewport();
  await page.screenshot({
    animations: "disabled",
    path: testInfo.outputPath("final-video-keyframe-1280.png"),
  });
});

test("过期内容选择更新后退出过期状态", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto(
    `/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan?scenario=node_stale`,
  );
  await page.getByRole("button", { name: "根据新内容更新" }).click();
  await expect(page.getByText("相关内容已经更新")).not.toBeVisible();
});

test("预算暂停可以确认并恢复", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}`);
  await expect(page.getByText("全自动制作已在费用门槛暂停")).not.toBeVisible();
  await page.goto(`/app/projects/${projectId}?scenario=budget_paused`);
  await page.getByRole("button", { name: "确认并继续" }).click();
  await expect(page.getByText("已恢复这一批任务")).toBeVisible();
});

test("未完成全部批准时不把说明文件当成交付物下载", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan`);
  await page.getByRole("button", { name: "确认教案" }).click();
  await expect(page.getByRole("link", { name: "安排 PPT 页面" })).toBeVisible();
  await page.goto(`/app/projects/${projectId}/delivery`);
  await expect(page.getByRole("button", { name: "等待交付包" }).first()).toBeDisabled();
});

test("项目里的备选作品可以切换", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/batches/mock-batch");
  const candidate = page.getByRole("button", { name: "备选作品 2" });
  await candidate.click();
  await expect(candidate).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(page.getByRole("button", { name: "备选作品 2" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("教案完整稿件修改保存后刷新仍保留", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan`);
  await page.getByRole("button", { name: "编辑" }).click();
  const lessonDocument = page.getByRole("textbox", { name: "教案正文" });
  const current = await lessonDocument.inputValue();
  await lessonDocument.fill(
    current.replace(
      "理解百分数表示一个数是另一个数的百分之几",
      "理解百分数的意义、读写与真实情境应用",
    ),
  );
  await page.getByRole("button", { name: "保存修改" }).click();
  await page.reload();
  await expect(page.getByTestId("markdown-preview")).toContainText(
    "理解百分数的意义、读写与真实情境应用",
  );
});

test("PPT 页面排序刷新后仍保留", async ({ page }) => {
  await loginAsTeacher(page);
  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-outline");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-outline`);
  await page.getByRole("button", { name: /拖动第 2 页/ }).press("ArrowDown");
  await page.reload();
  await expect(page.locator('input[aria-label="第 2 页标题"]')).toHaveValue("百格图里的 37%");
});

test("任务重新处理刷新后仍保留结果", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/tasks");
  await page.getByRole("button", { name: "等待处理" }).click();
  await page.getByRole("button", { name: "重新处理未完成内容" }).click();
  await page.reload();
  await page.getByRole("button", { name: "等待处理" }).click();
  const queuedTask = page.locator("article").filter({ hasText: "平行四边形的面积 · PPT 图片" });
  await expect(queuedTask.getByText("失败图片已开始重新处理")).toBeVisible();
  await expect(queuedTask.getByText("已进入等待处理")).toBeVisible();
  await expect(queuedTask.getByRole("link", { name: "去确认" })).toHaveCount(0);
});

test("PPT 正文编辑和确认刷新后仍保留", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-export`);
  await expect(page.getByText("正在打开课堂作品")).toBeHidden({ timeout: 30_000 });
  await expect(page.getByRole("link", { name: "去确认 PPT 正文" })).toBeVisible();
  await expect(page.getByRole("button", { name: "下载课件预览" })).toHaveCount(0);
  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-pages");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-pages`);
  await page.getByRole("button", { name: "1. 封面" }).click();
  const title = page.getByRole("heading", { name: "封面标题" });
  await title.fill("百分数就在身边");
  await title.blur();
  await page.getByRole("button", { name: "确认整套 PPT" }).click();
  await page.reload();
  await expect(page.getByRole("heading", { name: "封面标题" })).toHaveText("百分数就在身边");
  await expect(page.getByRole("button", { name: "重新编辑 PPT" })).toBeVisible();
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-export`);
  await expect(page.getByRole("heading", { level: 1, name: "课件预览" })).toHaveCount(1);
  await expect(page.getByText("最后一步 · 带走课堂作品", { exact: true })).toHaveCount(0);
  await expect(page.getByText("7 页课件预览", { exact: true })).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载课件预览" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("百分数的意义与读写_课堂课件预览.html");
  const downloadedPath = await download.path();
  if (!downloadedPath) throw new Error("未找到下载后的课件预览文件");
  const preview = await readFile(downloadedPath, "utf8");
  expect(preview.match(/<section\b/g)).toHaveLength(7);
});

test("粗分镜排序、文字和确认刷新后仍保留", async ({ page }) => {
  await loginAsTeacher(page);
  await unlockWorkbenchStep(page, projectId, lessonId, "rough-storyboard");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/rough-storyboard`);
  await page.getByRole("button", { name: /拖动三瓶果汁进入画面/ }).press("ArrowRight");
  await page
    .getByRole("textbox", { name: "三瓶果汁进入画面主要事件" })
    .fill("三瓶果汁依次进入画面，学生先观察标签差异。");
  await page.getByRole("button", { name: "确认故事镜头" }).click();
  await page.reload();
  await expect(page.getByRole("textbox", { name: "三瓶果汁进入画面主要事件" })).toHaveValue(
    "三瓶果汁依次进入画面，学生先观察标签差异。",
  );
  await expect(page.getByRole("button", { name: "故事镜头已确认" })).toBeDisabled();
  await expect(page.locator("article").first().getByRole("heading")).toHaveText("发现不同标签");
});

test("保存到项目的候选会出现在素材与成果并保留版本历史", async ({ page }) => {
  await loginAsTeacher(page);
  await page.goto("/app/creation/images");
  await page.getByRole("button", { name: "开始创作图片" }).click();
  await page.getByRole("button", { name: "就用这张" }).click();
  await page.getByRole("button", { name: "保存到项目" }).click();
  await page.getByRole("button", { name: "保存到这个位置" }).click();
  await expect(page.getByText(/已放进“.*”/, { exact: false })).toBeVisible();
  await page.goto(`/app/projects/${projectId}/results`);
  await expect(page.getByText("三瓶果汁主视觉", { exact: true })).toHaveCount(1);
  await expect(page.getByText("图片创作台 · 作品 1")).toBeVisible();
  await page.locator("button").filter({ hasText: "图片创作台 · 作品 1" }).click();
  await page.getByRole("button", { name: "替换当前版本" }).click();
  await page.reload();
  await page.getByRole("button", { name: "查看历史版本" }).click();
  await expect(page.getByText("版本 2 · 当前采用")).toBeVisible();
});

test("退出登录后刷新仍停留在登录页", async ({ page }) => {
  await loginAsTeacher(page);
  await page.getByRole("button", { name: "打开个人菜单" }).click();
  await expect(page.getByRole("menuitem", { name: "进入管理端" })).toHaveCount(0);
  await page.getByRole("menuitem", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
});
