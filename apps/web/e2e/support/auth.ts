import { expect, type Page } from "@playwright/test";

export async function loginAsTeacher(page: Page, targetPath = "/app/projects") {
  await page.goto(targetPath);
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "进入山海教育" })).toBeVisible();
  await page.getByLabel("学校访问码").fill("placeholder-contract-access-code");
  await page.getByRole("button", { name: "登录" }).click();
  await expect.poll(() => new URL(page.url()).pathname).toBe(targetPath);
}
