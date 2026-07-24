import { expect, test, type Page } from "@playwright/test";

function requiredEnvironment(name: string) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const accessCode = requiredEnvironment("SHANHAI_E2E_ACCESS_CODE");
const apiBaseUrl = process.env.SHANHAI_E2E_API_BASE_URL ?? "http://127.0.0.1:58080/api/v2";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("学校访问码").fill(accessCode);
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page).toHaveURL(/\/app\/projects$/);
  await expect(page.getByRole("heading", { name: "我的项目" })).toBeVisible();
}

test("login_creates_project_with_real_api", async ({ page }) => {
  await login(page);
  await page.goto("/app/projects/new");
  await page.getByRole("radio", { name: /暂不使用教材/ }).click();
  await page.getByLabel("项目名称").fill("认识1到5");
  await page.getByRole("textbox", { name: "知识点", exact: true }).fill("1到5的认识");
  await page.getByRole("button", { name: "创建课程项目" }).click();

  await expect(page).toHaveURL(/\/app\/projects\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "认识1到5" }).first()).toBeVisible();
});

test("refresh_restores_session", async ({ page }) => {
  await login(page);
  const beforeRefresh = await page.evaluate(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/auth/session`, { credentials: "include" });
    return (await response.json()) as { data: { session_id: string } };
  }, apiBaseUrl);

  await page.reload();
  await expect(page.getByRole("heading", { name: "我的项目" })).toBeVisible();
  const afterRefresh = await page.evaluate(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/auth/session`, { credentials: "include" });
    return (await response.json()) as { data: { session_id: string } };
  }, apiBaseUrl);
  expect(afterRefresh.data.session_id).toBe(beforeRefresh.data.session_id);
});

test("logout_blocks_writes", async ({ page }) => {
  await login(page);
  const current = await page.evaluate(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/auth/session`, { credentials: "include" });
    return (await response.json()) as { data: { csrf_token: string } };
  }, apiBaseUrl);

  await page.getByRole("button", { name: "打开个人菜单" }).click();
  await page.getByRole("menuitem", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login$/);

  const rejected = await page.evaluate(
    async ({ baseUrl, csrfToken }) => {
      const response = await fetch(`${baseUrl}/projects`, {
        body: JSON.stringify({ knowledge_point: "1到5的认识", title: "已登出" }),
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": "runtime-auth-logout-write",
          "X-CSRF-Token": csrfToken,
        },
        method: "POST",
      });
      const body = (await response.json()) as { error: { code: string } };
      return { body, status: response.status };
    },
    { baseUrl: apiBaseUrl, csrfToken: current.data.csrf_token },
  );
  expect(rejected.status).toBe(401);
  expect(rejected.body.error.code).toBe("AUTHENTICATION_REQUIRED");
});
