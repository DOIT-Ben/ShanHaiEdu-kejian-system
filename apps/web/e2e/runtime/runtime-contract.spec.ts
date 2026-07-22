import path from "node:path";
import { expect, test } from "@playwright/test";
import { installRuntimeApi, projectId } from "./support/runtimeApi";

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
  await expect(page.getByText("安全会话尚未就绪，请刷新后重试。")).toBeVisible();
  const submit = page.getByRole("button", { name: "创建项目并上传教材" });
  await expect(submit).toBeDisabled();
  await page.getByLabel("项目名称").fill("分数的意义");
  await page.getByRole("textbox", { name: "知识点", exact: true }).fill("分数与整体");
  await page.locator('input[type="file"]').setInputFiles(textbookPath);
  await expect(submit).toBeDisabled();

  await page.goto(`/app/projects/${projectId}/setup?jobId=01960000-0000-7000-8000-000000000003`);
  await expect(page.getByRole("button", { name: "取消任务" })).toBeDisabled();
  await expect(page.getByText("安全会话尚未就绪，暂时不能取消任务。请刷新后重试。")).toBeVisible();

  expect(api.writeRequests).toBe(0);
  expect(api.unhandled).toEqual([]);
});

test("真实模式在刷新后沿用创建意图并完成上传、任务和概览恢复", async ({ page }) => {
  await page.addInitScript(({ key }) => sessionStorage.setItem(key, "runtime-contract-csrf"), {
    key: runtimeContractTestCsrfKey,
  });
  const api = await installRuntimeApi(page, { failFirstUploadSession: true });

  await page.goto("/app/projects/new");
  await expect(page.getByText("安全会话尚未就绪，请刷新后重试。")).toHaveCount(0);
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
    new RegExp(`/app/projects/${projectId}/setup\\?jobId=01960000-0000-7000-8000-000000000003$`),
  );
  await expect(page.getByRole("heading", { name: "教材已经准备好" })).toBeVisible();
  await expect(page.getByText("系统已经整理出 1 个课时。")).toBeVisible();
  await expect.poll(() => api.jobStreamRequests).toBeGreaterThan(0);

  expect(api.createProjectRequests).toBe(1);
  expect(api.uploadSessionRequests).toBe(2);
  expect(api.uploadFileRequests).toBe(1);
  expect(api.confirmRequests).toBe(1);
  expect(api.idempotencyHeaders[2]).toBe(firstUploadIntent);
  expect(api.csrfHeaders.every((value) => value === "runtime-contract-csrf")).toBe(true);

  await page.getByRole("link", { name: "查看项目" }).click();
  await expect(page).toHaveURL(new RegExp(`/app/projects/${projectId}$`));
  await expect(page.getByRole("heading", { name: "认识百分数" }).first()).toBeVisible();
  await expect(page.getByText("百分数的意义", { exact: true }).first()).toBeVisible();
  await expect.poll(() => api.projectStreamRequests).toBeGreaterThan(0);
  expect(api.unhandled).toEqual([]);
});
