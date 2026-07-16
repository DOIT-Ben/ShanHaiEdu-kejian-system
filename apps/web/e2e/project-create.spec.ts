import { expect, login, test, useScenario } from "./helpers";

/** 流程一：登录 → 首页 → 项目列表 → 新建项目向导。 */
test.describe("登录与项目创建", () => {
  test("教师登录后看到首页概览", async ({ page }) => {
    await login(page);
    await expect(page.getByText(/欢迎回来/)).toBeVisible();
  });

  test("错误密码时展示可理解的错误信息", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/邮箱或工号/).fill("teacher@shanhai.edu");
    await page.getByLabel(/密码/).fill("wrong-password");
    await page.getByRole("button", { name: "登录" }).click();
    await expect(page.getByText(/账号或密码错误/)).toBeVisible();
  });

  test("创建项目：三步向导落库并进入项目", async ({ page }) => {
    await login(page);
    await page.goto("/app/projects");
    await page.getByRole("button", { name: "新建项目" }).first().click();
    await page.waitForURL("**/projects/new");

    await page.getByLabel(/项目名称/).fill("E2E·四年级下·小数的意义");
    await page.getByRole("button", { name: /下一步/ }).click();

    // 第二步跳过教材上传
    await page.getByRole("button", { name: /跳过，稍后上传/ }).click();

    await page.getByRole("button", { name: "完成创建，进入项目" }).click();
    await page.waitForURL(/\/app\/projects\/proj_/);
    await expect(page.getByText("E2E·四年级下·小数的意义").first()).toBeVisible();
  });

  test("空项目场景展示空状态", async ({ page }) => {
    await useScenario(page, "projects.empty");
    await login(page);
    await page.goto("/app/projects");
    await expect(page.getByText(/还没有项目|暂无项目/)).toBeVisible();
  });
});
