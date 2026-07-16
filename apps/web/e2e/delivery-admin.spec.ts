import { expect, test, useScenario } from "./helpers";
import type { Page } from "@playwright/test";

async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel(/邮箱或工号/).fill("admin@shanhai.edu");
  await page.getByLabel(/密码/).fill("demo1234");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/app**");
}

/** 流程四：交付打包 + 管理端模型配置（密钥掩码）。 */
test.describe("交付与管理端", () => {
  test("交付完成场景可见交付清单与成品包", async ({ page }) => {
    await useScenario(page, "delivery.completed");
    await loginAsAdmin(page);
    await page.goto("/app/projects/proj_alpha/delivery");
    await expect(page.getByText(/交付/).first()).toBeVisible();
    await expect(page.getByText(/已完成|成品包|下载/).first()).toBeVisible();
  });

  test("交付被阻塞场景展示阻塞原因", async ({ page }) => {
    await useScenario(page, "delivery.blocked");
    await loginAsAdmin(page);
    await page.goto("/app/projects/proj_alpha/delivery");
    await expect(page.getByText(/阻塞|未就绪|还不能打包|待完成/).first()).toBeVisible();
  });

  test("管理端 Provider 列表只显示密钥掩码，且可发起连接测试", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin/model-gateway/providers");
    await expect(page.getByText("启明文本云")).toBeVisible();
    // 掩码可见
    await expect(page.getByText("sk-****Kx3f")).toBeVisible();
    // 页面 DOM 中不允许出现任何看似完整的密钥
    const html = await page.content();
    expect(html).not.toMatch(/sk-[A-Za-z0-9]{20,}/);

    await page.getByRole("button", { name: "连接测试" }).first().click();
    await expect(page.getByText(/连接测试(通过|失败|发起失败)/).first()).toBeVisible({ timeout: 20_000 });
  });

  test("编辑 Provider 时密钥输入为 password 类型且不回显明文", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin/model-gateway/providers");
    await page.getByRole("button", { name: "编辑" }).first().click();
    const secret = page.getByLabel(/更新密钥/);
    await expect(secret).toHaveAttribute("type", "password");
    await expect(secret).toHaveValue("");
  });

  test("管理端仪表盘与审计页可访问", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin");
    await expect(page.getByText("今日调用次数")).toBeVisible();
    await page.goto("/admin/audit");
    await expect(page.getByText("审计日志")).toBeVisible();
  });

  test("教师访问管理端被拒绝", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/邮箱或工号/).fill("teacher@shanhai.edu");
    await page.getByLabel(/密码/).fill("demo1234");
    await page.getByRole("button", { name: "登录" }).click();
    await page.waitForURL("**/app**");
    await page.goto("/admin");
    await expect(page.getByText(/没有.*权限|403/).first()).toBeVisible();
  });
});
