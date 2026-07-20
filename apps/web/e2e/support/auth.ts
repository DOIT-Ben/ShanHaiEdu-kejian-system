import { expect, type Page } from "@playwright/test";

export async function loginAsTeacher(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("heading", { level: 1, name: "认识百分数" })).toBeVisible();
}

export async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("账号").fill("admin@example.edu");
  await page.getByLabel("密码").fill("admin-demo");
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page).toHaveURL(/\/admin\/content$/);
  await expect(page.getByRole("heading", { name: "内容中心" })).toBeVisible();
}
