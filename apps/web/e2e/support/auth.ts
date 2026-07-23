import { expect, type Page } from "@playwright/test";

export async function loginAsTeacher(page: Page) {
  await page.goto("/login");
  await page.getByRole("link", { name: "返回课堂工作区" }).click();
  await expect(page).toHaveURL(/\/app\/projects$/);
  await expect(page.getByRole("heading", { level: 1, name: "我的项目" })).toBeVisible();
}
