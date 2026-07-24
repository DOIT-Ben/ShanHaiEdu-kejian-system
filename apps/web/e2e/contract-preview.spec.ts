import { expect, test, type Page } from "@playwright/test";
import axe from "axe-core";
import { loginAsTeacher } from "./support/auth";

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000101";
const viewports = [
  { height: 900, width: 1440 },
  { height: 768, width: 1024 },
  { height: 844, width: 390 },
] as const;

async function assertNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
}

async function assertBasicAccessibility(page: Page) {
  await page.addScriptTag({ content: axe.source });
  const results = await page.evaluate(async () => {
    const axeApi = (globalThis as typeof globalThis & { axe: typeof axe }).axe;
    return axeApi.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
    });
  });
  expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
}

for (const viewport of viewports) {
  test(`Runtime 合同预览在 ${String(viewport.width)}px 保持同一路由和页面边界`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await loginAsTeacher(page, "/app/projects");
    await expect(page.getByTestId("project-row").first()).toContainText("认识百分数");
    await assertNoHorizontalOverflow(page);

    await loginAsTeacher(page, `/app/projects/${projectId}`);
    await expect(page.getByRole("heading", { name: "认识百分数" }).first()).toBeVisible();
    await assertNoHorizontalOverflow(page);

    await loginAsTeacher(page, `/app/projects/${projectId}/lessons/${lessonId}/work/lesson_plan`);
    await expect(page.getByText("百分数的意义", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("main")).not.toContainText("lesson_plan");
    await assertNoHorizontalOverflow(page);
    await assertBasicAccessibility(page);
  });
}

test("登录页只通过受控访问码建立合同预览会话", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "进入山海教育" })).toBeVisible();
  await expect(page.getByLabel("账号")).toHaveCount(0);
  await expect(page.getByLabel("密码")).toHaveCount(0);
  await expect(page.getByText(/demo|test|mock/i)).toHaveCount(0);
  await assertBasicAccessibility(page);
  await page.getByLabel("学校访问码").fill("placeholder-contract-access-code");
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page).toHaveURL(/\/app\/projects$/);
});

test("未覆盖的 Runtime API 请求被合同预览严格拒绝", async ({ page }) => {
  await loginAsTeacher(page, "/app/projects");
  const result = await page.evaluate(async () => {
    try {
      const response = await fetch("/api/v2/not-in-runtime-contract");
      return { ok: response.ok, status: response.status };
    } catch (reason) {
      return { error: reason instanceof Error ? reason.message : String(reason) };
    }
  });
  expect(result).toEqual({ ok: false, status: 500 });
});
