import { test, expect } from "@playwright/test";

/**
 * @responsive 1024 布局（docs/frontend/02 §6：1024–1279 右栏浮层，中央仍 ≥70%）。
 * 仅在 chromium-1024 项目运行（playwright.config grep）。
 */

const PROJECT = "00000000-0000-4000-8000-000000000101";
const LESSON = "00000000-0000-4000-8000-000000000202";

test("@responsive 工作台 1024：流程栏可折叠，画布不被右栏挤压", async ({ page }) => {
  await page.goto(`/app/projects/${PROJECT}/lessons/${LESSON}/work/lesson-plan-confirm?login=demo`);
  await expect(page.getByRole("heading", { name: "当前要做：修改并确认教案" })).toBeVisible();

  // 右侧栏默认折叠：展开后在 1024 下以浮层出现，不改变画布宽度
  const canvas = page.getByRole("heading", { name: "一、教学内容" });
  const before = (await canvas.boundingBox())!.width;
  await page.getByRole("button", { name: "展开右侧栏" }).click();
  await expect(page.getByText("生成要求", { exact: true })).toBeVisible();
  const after = (await canvas.boundingBox())!.width;
  expect(Math.abs(after - before)).toBeLessThan(24);

  // 流程栏可折叠，释放中央空间
  await page.getByRole("button", { name: "收起右侧栏" }).click();
  await page.getByRole("button", { name: "收起流程栏" }).click();
  await expect(page.getByRole("button", { name: "展开流程栏" })).toBeVisible();
});

test("@responsive 首页与项目页 1024 无横向滚动", async ({ page }) => {
  const targets: [string, string | RegExp][] = [
    ["/app", "把一份教材，变成完整的课堂作品"],
    [`/app/projects/${PROJECT}`, "课时进度"],
    ["/app/creation", "今天想创作什么？"],
  ];
  for (const [path, marker] of targets) {
    await page.goto(`${path}?login=demo`);
    await expect(page.getByText(marker).first()).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, path).toBeLessThanOrEqual(0);
  }
});
