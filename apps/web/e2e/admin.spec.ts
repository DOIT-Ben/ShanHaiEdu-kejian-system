import { test, expect, type Page } from "@playwright/test";

/** 管理端流程：RBAC、密钥只写、内容包发布链。 */

async function loginAdmin(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "系统管理员" }).click();
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/\/app/);
}

test("教师访问管理端被拦截", async ({ page }) => {
  await page.goto("/admin/models?login=demo");
  await expect(page.getByText("没有管理权限")).toBeVisible();
});

test("模型服务：密钥只显示状态与尾号；替换密钥不回显明文", async ({ page }) => {
  await loginAdmin(page);
  await page.goto("/admin/models");
  await expect(page.getByRole("heading", { name: "模型服务" })).toBeVisible();
  await expect(page.getByText(/尾号 [A-Za-z0-9]{2,6}/).first()).toBeVisible();

  const secret = "e2e-secret-rotation-2026";
  await page.getByRole("button", { name: "配置" }).last().click();
  const dialog = page.getByRole("dialog");
  await dialog.getByPlaceholder(/输入新密钥/).fill(secret);
  await dialog.getByRole("button", { name: "保存配置" }).click();
  await expect(dialog).toBeHidden();
  // 尾号已更新，页面任何位置都没有明文
  await expect(page.getByText(`尾号 ${secret.slice(-4)}`).first()).toBeVisible();
  await expect(page.locator("body")).not.toContainText(secret);
});

test("内容中心：试运行未通过的包发布被拦截", async ({ page }) => {
  await loginAdmin(page);
  await page.goto("/admin/content");
  await page.getByRole("link", { name: /简案结构/ }).click();
  await expect(page.getByRole("heading", { name: "结构预览" })).toBeVisible();
  // 五部分简案结构由内容定义免改码渲染
  await expect(page.getByRole("heading", { name: "一、教学目标" })).toBeVisible();
  await page.getByRole("button", { name: "发布新版本" }).click();
  await expect(page.getByText(/试运行未通过/).first()).toBeVisible();
});

test("运行与费用 / 用户 / 审计 页面可达", async ({ page }) => {
  await loginAdmin(page);
  await page.goto("/admin/usage");
  await expect(page.getByRole("heading", { name: "运行与费用" })).toBeVisible();
  await page.goto("/admin/users");
  await expect(page.getByText("教师", { exact: true }).first()).toBeVisible();
  await page.goto("/admin/audit");
  await expect(page.getByRole("heading", { name: "审计记录" })).toBeVisible();
});
