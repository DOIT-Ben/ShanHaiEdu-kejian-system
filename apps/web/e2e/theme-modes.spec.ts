import { expect, test, type Page, type TestInfo } from "@playwright/test";
import axe from "axe-core";
import { loginAsAdmin, loginAsTeacher } from "./support/auth";
import { unlockWorkbenchStep } from "./support/runtime";

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000101";

const themes = [
  {
    background: "rgb(243, 247, 238)",
    label: "护眼",
    mode: "eye-care",
    themeColor: "#f3f7ee",
  },
  { background: "rgb(255, 255, 255)", label: "白天", mode: "day", themeColor: "#ffffff" },
  {
    background: "rgb(39, 43, 41)",
    label: "黑夜",
    mode: "night",
    themeColor: "#272b29",
  },
] as const;

async function chooseTheme(page: Page, label: string, mode: string) {
  await page.getByRole("button", { name: /^切换主题，当前/ }).click();
  await page.getByRole("menuitemradio", { name: `${label}模式` }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", mode);
  await expect(page.getByRole("button", { name: `切换主题，当前${label}模式` })).toBeVisible();
}

async function expectNoAccessibilityViolations(page: Page) {
  await page.addScriptTag({ content: axe.source });
  const violations = await page.evaluate(async () => {
    const results = await (window as typeof window & { axe: typeof axe }).axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
    });
    return results.violations.map(({ help, id, impact }) => ({ help, id, impact }));
  });
  expect(violations).toEqual([]);
}

test("教师端三种主题全局切换并持久化", async ({ page }, testInfo: TestInfo) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await loginAsTeacher(page);

  for (const theme of themes) {
    await chooseTheme(page, theme.label, theme.mode);
    await expect(page.locator("body")).toHaveCSS("background-color", theme.background);
    await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute(
      "content",
      theme.themeColor,
    );
    await expectNoAccessibilityViolations(page);
    await page.screenshot({
      animations: "disabled",
      fullPage: true,
      path: testInfo.outputPath(`teacher-${theme.mode}-1440.png`),
    });
  }

  await page.getByRole("button", { name: "切换主题，当前黑夜模式" }).click();
  await expect(page.locator('[role="menu"]')).toBeVisible();
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: testInfo.outputPath("teacher-theme-menu-night-1440.png"),
  });
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "打开个人菜单" }).click();
  await expect(page.getByText("界面主题", { exact: true })).toBeVisible();
  await page.getByRole("menuitemradio", { name: "白天模式" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "day");
  await chooseTheme(page, "黑夜", "night");

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "night");
  await expect(page.getByRole("button", { name: "切换主题，当前黑夜模式" })).toBeVisible();

  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-pages");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-pages`);
  await page.getByRole("button", { name: /^2\. 生活中的百分数$/ }).click();
  await expect(page.getByLabel("第 2 页正文").locator("..")).toHaveCSS(
    "background-color",
    "rgb(255, 255, 255)",
  );
  await expect(page.getByLabel("第 2 页正文")).toHaveCSS("color", "rgb(92, 82, 72)");
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: testInfo.outputPath("ppt-artifact-night-1440.png"),
  });
});

test("登录页与移动管理端共享同一主题控制", async ({ page }, testInfo: TestInfo) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await page.goto("/login");
  await chooseTheme(page, "黑夜", "night");
  await expectNoAccessibilityViolations(page);
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: testInfo.outputPath("login-night-390.png"),
  });

  await loginAsAdmin(page);
  await expect(page.locator("html")).toHaveAttribute("data-theme", "night");
  await expect(page.getByRole("button", { name: "切换主题，当前黑夜模式" })).toBeVisible();
  await expectNoAccessibilityViolations(page);
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: testInfo.outputPath("admin-night-390.png"),
  });
});

test("浅色主题的反色标题与 PPT 封面满足可读性", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await page.goto("/login");

  for (const theme of themes.slice(0, 2)) {
    await chooseTheme(page, theme.label, theme.mode);
    await expectNoAccessibilityViolations(page);
  }
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: testInfo.outputPath("login-day-1440.png"),
  });

  await loginAsTeacher(page);
  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-pages");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-pages`);
  await page.getByRole("button", { name: /^1\. 封面$/ }).click();
  for (const theme of themes.slice(0, 2)) {
    await chooseTheme(page, theme.label, theme.mode);
    await expectNoAccessibilityViolations(page);
  }
  await page.screenshot({
    animations: "disabled",
    path: testInfo.outputPath("ppt-cover-day-1440.png"),
  });
});

test("390px 保留 PPT 更多操作并提示管理端横向内容", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await loginAsTeacher(page);
  await page.getByRole("button", { name: "打开个人菜单" }).click();
  await page.getByRole("menuitemradio", { name: "黑夜模式" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "night");
  await chooseTheme(page, "护眼", "eye-care");
  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-pages");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-pages`);
  const moreActions = page.getByRole("button", { name: "更多页面操作" });
  const moreBox = await moreActions.boundingBox();
  expect(moreBox).not.toBeNull();
  expect((moreBox?.x ?? 0) + (moreBox?.width ?? 0)).toBeLessThanOrEqual(390);
  await page.screenshot({
    animations: "disabled",
    path: testInfo.outputPath("ppt-toolbar-390.png"),
  });

  await loginAsAdmin(page);
  await expect(page.getByTestId("admin-navigation-scroll-next")).toBeVisible();
  const contentScrollNext = page.getByTestId("admin-content-table-scroll-next");
  const contentScrollPrevious = page.getByTestId("admin-content-table-scroll-next-previous");
  const contentScroll = page.getByRole("region", { name: "内容包列表" });
  await expect(contentScrollNext).toBeVisible();
  await contentScroll.focus();
  await expect(contentScroll).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(() => contentScroll.evaluate((element) => element.scrollLeft))
    .toBeGreaterThan(0);
  await expect(contentScrollPrevious).toBeVisible();
  await contentScroll.evaluate((element) => {
    element.scrollLeft = element.scrollWidth;
    element.dispatchEvent(new Event("scroll"));
  });
  await expect(contentScrollNext).toBeHidden();
  await contentScroll.evaluate((element) => {
    element.scrollLeft = 0;
    element.dispatchEvent(new Event("scroll"));
  });
  await expect(contentScrollNext).toBeVisible();
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: testInfo.outputPath("admin-scroll-hints-390.png"),
  });
});

test("首屏、跨标签重置与夜间遮罩使用同一主题事实", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("shanhaiedu.theme", "night"));
  await page.goto("/login");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "night");
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute("content", "#272b29");

  const secondPage = await page.context().newPage();
  await secondPage.goto("/login");
  await expect(secondPage.getByRole("button", { name: "切换主题，当前黑夜模式" })).toBeVisible();
  await page.evaluate(() => localStorage.removeItem("shanhaiedu.theme"));
  await expect(secondPage.locator("html")).toHaveAttribute("data-theme", "eye-care");
  await secondPage.close();

  await loginAsTeacher(page);
  await chooseTheme(page, "黑夜", "night");
  await page.getByRole("button", { name: "搜索" }).click();
  await expect(page.getByTestId("global-search-overlay")).toHaveCSS(
    "background-color",
    "rgba(8, 10, 9, 0.58)",
  );
});
