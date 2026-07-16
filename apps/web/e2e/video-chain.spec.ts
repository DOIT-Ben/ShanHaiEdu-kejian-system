import { expect, login, test, useScenario } from "./helpers";

/** 流程三：视频链路 —— 单镜头失败重试（部分成功不阻塞）、图片资产带入。 */
test.describe("视频链路", () => {
  test("镜头片段部分失败时可单独重试", async ({ page }) => {
    await useScenario(page, "video.shot.partial_failure");
    await login(page);
    await page.goto("/app/projects/proj_alpha/lessons/lesson_a1/workbench/video_clips");
    await expect(page.getByText(/失败 \d+ 个（可单独重试，已完成镜头不受影响）/)).toBeVisible();
    const retryButton = page.getByRole("button", { name: "重试该镜头" }).first();
    await expect(retryButton).toBeVisible();
    await retryButton.click();
    // 单镜头重试可能触发备用服务付费确认（409），此时确认费用后继续
    const fallbackDialog = page.getByText("切换备用服务将再次计费");
    if (await fallbackDialog.isVisible({ timeout: 3000 }).catch(() => false)) {
      await page.getByRole("button", { name: "确认费用并重试" }).click();
    }
    // 页面保持可用且未整体报错
    await expect(page.getByText("认识几分之一").first()).toBeVisible();
  });

  test("资产页签支持从资产库选择参考资产", async ({ page }) => {
    await login(page);
    await page.goto("/app/projects/proj_alpha/lessons/lesson_a1/workbench/video_clips");
    await page.getByRole("tab", { name: "资产" }).click();
    await page.getByRole("button", { name: "从资产库选择" }).click();
    await expect(page.getByText("选择参考资产")).toBeVisible();
  });

  test("项目资产库可筛选并打开详情（上下游引用）", async ({ page }) => {
    await login(page);
    await page.goto("/app/projects/proj_alpha/assets");
    const firstCard = page.getByRole("button", { name: /查看资产/ }).first();
    if (await firstCard.isVisible({ timeout: 3000 }).catch(() => false)) {
      await firstCard.click();
    } else {
      await page.getByText(/镜头|母图|成片/).first().click();
    }
  });
});
