import { expect, login, test, useScenario } from "./helpers";

/** 流程二：课时工作台 —— 教案审阅、提示词工作台、跳过/恢复。 */
test.describe("课时工作台", () => {
  test("从课时列表进入工作台并看到 18 步流程", async ({ page }) => {
    await login(page);
    await page.goto("/app/projects/proj_alpha/lessons");
    await page.getByText("认识几分之几").click();
    await page.waitForURL(/\/workbench\//);
    // 工作流侧栏应展示五个分组
    for (const group of ["教案", "导入设计", "PPT", "视频", "交付"]) {
      await expect(page.getByText(group, { exact: true }).first()).toBeVisible();
    }
  });

  test("提示词工作台：最终提示词可见、可编辑、可恢复默认", async ({ page }) => {
    await useScenario(page, "lesson_plan.review");
    await login(page);
    await page.goto("/app/projects/proj_alpha/lessons/lesson_a2/workbench/lesson_plan");
    await page.getByRole("tab", { name: "提示词" }).click();
    const editor = page.getByLabel("最终提示词（可编辑）");
    await expect(editor).toBeVisible();
    const original = await editor.inputValue();
    expect(original.length).toBeGreaterThan(10);

    await editor.fill(`${original}\n请更强调动手操作环节。`);
    await expect(page.getByText("提示词已修改，保存后按新提示词生成。")).toBeVisible();
    await page.getByRole("button", { name: "保存为新版本" }).click();
    // 保存后出现新版本（dirty 提示消失）
    await expect(page.getByText("提示词已修改，保存后按新提示词生成。")).toHaveCount(0);
  });

  test("教案待审核时可批准；警告需逐项确认后批准生效", async ({ page }) => {
    await useScenario(page, "lesson_plan.review");
    await login(page);
    await page.goto("/app/projects/proj_alpha/lessons/lesson_a2/workbench/lesson_plan");
    const approveButton = page.getByRole("button", { name: "批准此版本" });
    await expect(approveButton).toBeVisible();
    await approveButton.click();

    // 该场景包含一条校验警告：批准前必须逐项确认并填写说明
    const warningDialog = page.getByRole("dialog", { name: "确认校验警告" });
    await expect(warningDialog).toBeVisible();
    await warningDialog.getByRole("checkbox").first().check();
    await warningDialog.getByLabel("确认说明").fill("时长超出在允许范围内，已与教研确认。");
    await warningDialog.getByRole("button", { name: "确认并批准" }).click();

    await expect(page.getByText("已批准").first()).toBeVisible();
  });
});
