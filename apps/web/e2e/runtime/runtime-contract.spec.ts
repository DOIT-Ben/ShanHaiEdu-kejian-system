import path from "node:path";
import { expect, test } from "@playwright/test";
import {
  artifactId,
  fileAssetVersionId,
  installRuntimeApi,
  jobId,
  lessonId,
  materialId,
  projectId,
} from "./support/runtimeApi";

const textbookPath = path.join(process.cwd(), "e2e", "runtime", "fixtures", "textbook.pdf");
const runtimeContractTestCsrfKey = "shanhaiedu.runtime-contract-test.csrf";

test("真实模式首页、项目概览和安全会话门禁只消费合同接口", async ({ page }) => {
  const api = await installRuntimeApi(page, { jobStatus: "running" });

  await page.goto("/app");
  await expect(page.getByRole("heading", { level: 1, name: "认识百分数" })).toBeVisible();
  await page.getByRole("button", { name: "搜索" }).click();
  await expect(page.getByText("当前没有可搜索的项目或功能。")).toBeVisible();
  await expect(page.getByRole("link", { name: "第 1 课时 · 百分数的意义" })).toHaveCount(0);
  await page.getByRole("button", { name: "关闭搜索" }).click();
  await page.getByRole("button", { name: "通知", exact: true }).click();
  await expect(page.getByText("暂无新通知")).toBeVisible();
  await expect(page.getByRole("link", { name: "教案已完成检查" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByText("认识百分数", { exact: true }).first()).toBeVisible();
  await page.getByRole("link", { name: "继续制作" }).click();
  await expect(page).toHaveURL(new RegExp(`/app/projects/${projectId}$`));
  await expect(page.getByRole("heading", { name: "认识百分数" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "课时安排" })).toBeVisible();
  await expect.poll(() => api.projectStreamRequests).toBeGreaterThan(0);

  await page.goto("/app/projects/new");
  await expect(page.getByText("当前会话仅支持查看，无法创建项目。")).toBeVisible();
  const submit = page.getByRole("button", { name: "创建项目并上传教材" });
  await expect(submit).toBeDisabled();
  await page.getByLabel("项目名称").fill("分数的意义");
  await page.getByRole("textbox", { name: "知识点", exact: true }).fill("分数与整体");
  await page.locator('input[type="file"]').setInputFiles(textbookPath);
  await expect(submit).toBeDisabled();

  await page.goto(`/app/projects/${projectId}/setup?jobId=01960000-0000-7000-8000-000000000003`);
  await expect(page.getByRole("button", { name: "取消任务" })).toBeDisabled();
  await expect(page.getByRole("status")).toHaveText("当前会话只能查看任务进度，暂时无法取消任务。");

  expect(api.writeRequests).toBe(0);
  expect(api.unhandled).toEqual([]);
});

test("真实模式在刷新后沿用创建意图并完成上传、任务和概览恢复", async ({ page }) => {
  await page.addInitScript(({ key }) => sessionStorage.setItem(key, "runtime-contract-csrf"), {
    key: runtimeContractTestCsrfKey,
  });
  const api = await installRuntimeApi(page, { failFirstUploadSession: true });

  await page.goto("/app/projects/new");
  await expect(page.getByText("当前会话仅支持查看，无法创建项目。")).toHaveCount(0);
  await page.getByLabel("项目名称").fill("认识百分数");
  await page.getByRole("textbox", { name: "知识点", exact: true }).fill("百分数的意义");
  await page.locator('input[type="file"]').setInputFiles(textbookPath);
  await page.getByRole("button", { name: "创建项目并上传教材" }).click();

  await expect(page.getByRole("alert")).toContainText("教材上传入口暂时不可用");
  expect(api.createProjectRequests).toBe(1);
  expect(api.uploadSessionRequests).toBe(1);
  const firstUploadIntent = api.idempotencyHeaders[1];
  expect(firstUploadIntent).toBeTruthy();

  await page.reload();
  await expect(page.getByRole("status", { name: "已保存的课程进度" })).toContainText(
    "重新选择同一份 PDF 后可以继续上传",
  );
  await expect(page.getByLabel("项目名称")).toHaveValue("认识百分数");
  await expect(page.getByRole("textbox", { name: "知识点", exact: true })).toHaveValue(
    "百分数的意义",
  );
  await page.locator('input[type="file"]').setInputFiles(textbookPath);
  await page.getByRole("button", { name: "创建项目并上传教材" }).click();

  await expect(page).toHaveURL(
    new RegExp(`/app/projects/${projectId}/setup\\?jobId=${jobId}&materialId=${materialId}$`),
  );
  await expect(page.getByRole("heading", { name: "教材已经准备好" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "课时已经可以核对" })).toBeVisible();
  await expect(page.getByText("项目中已经保存 1 个课时，可以进入课时页核对和编辑。")).toBeVisible();
  await expect(page.getByRole("link", { name: "查看课时" })).toBeVisible();
  expect(api.jobReads).toBeGreaterThan(0);
  expect(api.jobStreamRequests).toBe(0);

  expect(api.createProjectRequests).toBe(1);
  expect(api.uploadSessionRequests).toBe(2);
  expect(api.uploadFileRequests).toBe(1);
  expect(api.confirmRequests).toBe(1);
  expect(api.idempotencyHeaders[2]).toBe(firstUploadIntent);
  expect(api.csrfHeaders.every((value) => value === "runtime-contract-csrf")).toBe(true);

  await page.getByRole("link", { name: "查看教材详情" }).click();
  await expect(page).toHaveURL(new RegExp(`/app/projects/${projectId}/materials/${materialId}$`));
  await expect(page.getByText("8 页").first()).toBeVisible();
  expect(api.materialFileReads).toBeGreaterThan(0);
  expect(api.materialParseReads).toBeGreaterThan(0);

  await page.getByRole("link", { name: "返回项目" }).click();
  await expect(page).toHaveURL(new RegExp(`/app/projects/${projectId}$`));
  await expect(page.getByRole("heading", { name: "认识百分数" }).first()).toBeVisible();
  await expect(page.getByText("百分数的意义", { exact: true }).first()).toBeVisible();
  await expect.poll(() => api.projectStreamRequests).toBeGreaterThan(0);
  expect(api.unhandled).toEqual([]);
});

test("真实模式接入课时、只读内容版本、素材包和任务的现行合同", async ({ page }) => {
  await page.addInitScript(({ key }) => sessionStorage.setItem(key, "runtime-contract-csrf"), {
    key: runtimeContractTestCsrfKey,
  });
  const api = await installRuntimeApi(page, { jobStatus: "running" });

  await page.goto(`/app/projects/${projectId}/lessons`);
  const title = page.getByLabel("课时 1 名称");
  await title.fill("百分数初步认识");
  await page.getByRole("button", { name: "保存课时集合" }).click();
  await expect.poll(() => api.lessonCollectionWrites).toBe(1);
  await expect(title).toHaveValue("百分数初步认识");
  expect(api.ifMatchHeaders).toContain('"lessons-v1"');

  await page.getByRole("checkbox", { name: "课堂视频" }).uncheck();
  await page.getByRole("button", { name: "保存百分数初步认识的分支" }).click();
  await expect.poll(() => api.lessonBranchWrites).toBe(1);
  expect(api.ifMatchHeaders).toContain('"lesson-v1"');

  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/lesson_plan`);
  await expect(page.getByText("这一步暂时没有可显示的制作进度。")).toBeVisible();
  await expect(page.getByRole("main")).not.toContainText("lesson_plan");

  await page.goto(
    `/app/projects/${projectId}/assets?fileVersionId=${fileAssetVersionId}&assetLabel=${encodeURIComponent("课堂封面")}`,
  );
  await expect(page.getByText("素材包包含 1 个素材位置。")).toBeVisible();
  await page.getByRole("button", { name: "放入图片位置 1" }).click();
  await expect.poll(() => api.assetBinds).toBe(1);
  await page.getByRole("button", { name: "移除图片素材 1" }).click();
  await expect.poll(() => api.assetUnbinds).toBe(1);
  expect(api.assetSlotReads).toBeGreaterThan(0);
  expect(api.assetPackageReads).toBeGreaterThan(0);

  await page.goto(`/app/projects/${projectId}/artifacts/${artifactId}`);
  await expect(page.getByRole("heading", { name: "课时教案" })).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "草稿保存、版本提交和批准均已停用" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "保存草稿" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "提交当前草稿" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "批准当前版本" })).toHaveCount(0);
  expect(api.artifactSubmits).toBe(0);
  expect(api.artifactApprovals).toBe(0);
  expect(api.artifactReads).toBeGreaterThan(0);

  await page.goto(`/app/projects/${projectId}/jobs/${jobId}`);
  await expect(page.getByRole("heading", { name: "任务正在处理" })).toBeVisible();
  await page.getByRole("button", { name: "取消任务" }).click();
  await expect.poll(() => api.jobCancelRequests).toBe(1);
  await expect.poll(() => api.jobStreamRequests).toBeGreaterThan(0);

  expect(api.csrfHeaders.every((value) => value === "runtime-contract-csrf")).toBe(true);
  expect(api.idempotencyHeaders.every(Boolean)).toBe(true);
  expect(api.unhandled).toEqual([]);
});

test("教材解析完成但没有课时时保持真实阻断", async ({ page }) => {
  const api = await installRuntimeApi(page, { emptyLessons: true, jobStatus: "succeeded" });

  await page.goto(`/app/projects/${projectId}/setup?jobId=${jobId}&materialId=${materialId}`);

  await expect(page.getByRole("heading", { name: "教材已经准备好" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "课时尚未建立" })).toBeVisible();
  await expect(page.getByText(/课时创建和教案生成暂不可用/)).toBeVisible();
  await expect(page.getByRole("link", { name: "返回项目" })).toBeVisible();
  await expect(page.getByRole("link", { name: "查看课时" })).toHaveCount(0);
  expect(api.jobStreamRequests).toBe(0);
  expect(api.unhandled).toEqual([]);
});

test("真实模式如实显示任务失败且不暴露内部错误代码", async ({ page }) => {
  const api = await installRuntimeApi(page, { jobStatus: "failed" });

  await page.goto(`/app/projects/${projectId}/jobs/${jobId}`);
  await expect(page.getByRole("heading", { name: "任务没有完成" })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("任务没有完成");
  await expect(page.getByRole("alert")).not.toContainText("MATERIAL_PARSE_FAILED");
  expect(api.unhandled).toEqual([]);
});

test("真实模式在任务事件后重新读取 REST 终态并停止订阅", async ({ page }) => {
  const api = await installRuntimeApi(page, {
    completeJobAfterStream: true,
    jobStatus: "running",
  });

  await page.goto(`/app/projects/${projectId}/jobs/${jobId}`);

  await expect.poll(() => api.jobStreamRequests).toBeGreaterThan(0);
  await expect.poll(() => api.jobReads).toBeGreaterThan(1);
  await expect(page.getByRole("heading", { name: "任务已经完成" })).toBeVisible({
    timeout: 3_000,
  });

  const terminalStreamCount = api.jobStreamRequests;
  expect(terminalStreamCount).toBe(1);
  await page.waitForTimeout(1_250);
  expect(api.jobStreamRequests).toBe(terminalStreamCount);
  expect(api.unhandled).toEqual([]);
});

test("真实模式在取消响应丢失后复用原幂等意图", async ({ page }) => {
  await page.addInitScript(({ key }) => sessionStorage.setItem(key, "runtime-contract-csrf"), {
    key: runtimeContractTestCsrfKey,
  });
  const api = await installRuntimeApi(page, {
    failFirstJobCancelAfterAccept: true,
    jobStatus: "running",
  });

  await page.goto(`/app/projects/${projectId}/jobs/${jobId}`);
  await page.getByRole("button", { name: "取消任务" }).click();
  await expect(page.getByRole("alert")).toContainText("网络连接失败");
  await page.getByRole("button", { name: "重试取消" }).click();

  await expect.poll(() => api.jobCancelRequests).toBe(2);
  expect(api.jobCancelIdempotencyHeaders).toHaveLength(2);
  expect(api.jobCancelIdempotencyHeaders[0]).toBeTruthy();
  expect(api.jobCancelIdempotencyHeaders[1]).toBe(api.jobCancelIdempotencyHeaders[0]);
  expect(api.unhandled).toEqual([]);
});

test("真实模式可只用课程锚点创建项目且不伪造教材任务", async ({ page }) => {
  await page.addInitScript(({ key }) => sessionStorage.setItem(key, "runtime-contract-csrf"), {
    key: runtimeContractTestCsrfKey,
  });
  const api = await installRuntimeApi(page);

  await page.goto("/app/projects/new");
  await page.getByRole("radio", { name: /暂不使用教材/ }).click();
  await page.getByLabel("项目名称").fill("生活中的百分数");
  await page.getByRole("textbox", { name: "知识点", exact: true }).fill("百分数的实际应用");
  await expect(page.getByRole("region", { name: "课程锚点摘要" })).toContainText(
    "六年级 · 人教版 · 百分数的实际应用",
  );
  await page.getByRole("button", { name: "创建课程项目" }).click();

  await expect(page).toHaveURL(new RegExp(`/app/projects/${projectId}$`));
  await expect(page.getByRole("heading", { name: "生活中的百分数" }).first()).toBeVisible();
  expect(api.createProjectRequests).toBe(1);
  expect(api.uploadSessionRequests).toBe(0);
  expect(api.uploadFileRequests).toBe(0);
  expect(api.confirmRequests).toBe(0);
  expect(api.unhandled).toEqual([]);
});

test("真实模式开放独立创作并只在结果读取缺口处阻断", async ({ page }) => {
  await page.addInitScript(({ key }) => sessionStorage.setItem(key, "runtime-contract-csrf"), {
    key: runtimeContractTestCsrfKey,
  });
  const api = await installRuntimeApi(page, {
    completeJobAfterStream: true,
    jobStatus: "running",
  });

  await page.goto("/app/creation");
  await expect(page.getByRole("heading", { name: "今天想创作什么" })).toBeVisible();
  await page.getByRole("link", { name: /画一张教学图片/ }).click();
  await expect(page).toHaveURL(/\/app\/creation\/images$/);
  await page.getByLabel("描述你想创作的图片").fill("画一张用百格图解释百分数的教学图片");
  await page.getByRole("button", { name: "开始创作图片" }).click();

  await expect(page.getByRole("heading", { name: "作品生成任务已完成" })).toBeVisible();
  await expect(page.getByText(/暂时不能在这里查看、选用或保存到项目/)).toBeVisible();
  expect(api.creationBatchRequests).toBe(1);
  expect(api.creationPromptRequests).toBe(1);
  expect(api.creationGenerateRequests).toBe(1);
  expect(api.jobReads).toBeGreaterThan(0);
  expect(api.jobStreamRequests).toBeGreaterThan(0);
  expect(api.csrfHeaders.every((value) => value === "runtime-contract-csrf")).toBe(true);
  expect(api.idempotencyHeaders.every(Boolean)).toBe(true);
  expect(api.unhandled).toEqual([]);
});
