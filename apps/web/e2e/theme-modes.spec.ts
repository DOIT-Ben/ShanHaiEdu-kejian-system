import { expect, test, type Page, type TestInfo } from "@playwright/test";
import axe from "axe-core";
import { loginAsAdmin, loginAsTeacher } from "./support/auth";
import { unlockWorkbenchStep } from "./support/runtime";

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000101";

const themes = [
  {
    canvas: "oklch(0.9706 0.0126 126.4)",
    label: "护眼",
    mode: "eye-care",
    themeColor: "#f3f7ee",
  },
  { canvas: "oklch(1 0 0)", label: "白天", mode: "day", themeColor: "#ffffff" },
  {
    canvas: "oklch(0.2843 0.0067 164.5)",
    label: "黑夜",
    mode: "night",
    themeColor: "#272b29",
  },
  {
    canvas: "oklch(0.962 0.007 245)",
    label: "高级简约",
    mode: "atelier",
    themeColor: "#f3f4f2",
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
    return results.violations.map(({ help, id, impact, nodes }) => ({
      help,
      id,
      impact,
      nodes: nodes.map((node) => node.html),
    }));
  });
  expect(violations).toEqual([]);
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
}

test("教师端四种主题全局切换并持久化", async ({ page }, testInfo: TestInfo) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await loginAsTeacher(page);

  for (const theme of themes) {
    await chooseTheme(page, theme.label, theme.mode);
    await expect
      .poll(() =>
        page
          .locator("html")
          .evaluate((element) =>
            getComputedStyle(element).getPropertyValue("--sh-surface-canvas").trim(),
          ),
      )
      .toBe(theme.canvas);
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

  await page.getByRole("button", { name: "切换主题，当前高级简约模式" }).click();
  await expect(page.locator('[role="menu"]')).toBeVisible();
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: testInfo.outputPath("teacher-theme-menu-atelier-1440.png"),
  });
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "打开个人菜单" }).click();
  await expect(page.getByText("界面主题", { exact: true })).toBeVisible();
  await page.getByRole("menuitemradio", { name: "白天模式" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "day");
  await chooseTheme(page, "高级简约", "atelier");

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "atelier");
  await expect(page.getByRole("button", { name: "切换主题，当前高级简约模式" })).toBeVisible();

  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-pages");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-pages`);
  await page.getByRole("button", { name: /^2\. 生活中的百分数$/ }).click();
  await expect(page.getByLabel("第 2 页正文").locator("..")).toHaveCSS(
    "background-color",
    "oklch(1 0 0)",
  );
  await expect(page.getByLabel("第 2 页正文")).toHaveCSS("color", "oklch(0.4453 0.0207 67.3)");
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: testInfo.outputPath("ppt-artifact-atelier-1440.png"),
  });
});

test("高级简约主题在核心工作页保持统一层级", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 900, width: 1280 });
  await loginAsTeacher(page);
  await chooseTheme(page, "高级简约", "atelier");

  const pages = [
    { heading: "认识百分数", name: "atelier-home-1280", path: "/app" },
    { heading: "我的项目", name: "atelier-projects-1280", path: "/app/projects" },
    {
      heading: "百分数的意义",
      name: "atelier-workbench-1280",
      path: `/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan`,
    },
    { heading: "图片创作台", name: "atelier-creation-1280", path: "/app/creation/images" },
  ];

  for (const entry of pages) {
    await page.goto(entry.path);
    await expect(page.getByRole("heading", { name: entry.heading }).first()).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "atelier");
    await expectNoHorizontalOverflow(page);
    await expectNoAccessibilityViolations(page);
    await page.screenshot({
      animations: "disabled",
      fullPage: true,
      path: testInfo.outputPath(`${entry.name}.png`),
    });
  }

  await page.setViewportSize({ height: 844, width: 390 });
  await page.goto("/app/creation/images");
  await expect(page.getByRole("heading", { level: 1, name: "图片创作台" })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await expectNoAccessibilityViolations(page);
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: testInfo.outputPath("atelier-creation-390.png"),
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
  const groupedActions = page.getByRole("button", { name: "检查与编辑" });
  await expect(groupedActions).toBeInViewport();
  await groupedActions.click();
  await expect(page.getByRole("menuitem", { name: "查看检查结果" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "查看参考内容" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "编辑内容要求" })).toBeVisible();
  await page.keyboard.press("Escape");
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
  await expect
    .poll(() =>
      page
        .locator("html")
        .evaluate((element) =>
          getComputedStyle(element).getPropertyValue("--sh-overlay-scrim").trim(),
        ),
    )
    .toBe("oklch(0.16 0.008 160 / 58%)");
});
