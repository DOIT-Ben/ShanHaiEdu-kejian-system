import { expect, test, type Page } from "@playwright/test";
import { loginAsTeacher } from "./support/auth";
import { unlockWorkbenchStep } from "./support/runtime";

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000101";

async function visibleHeightWithin(page: Page, childSelector: string, parentSelector: string) {
  return page.evaluate(
    ({ child, parent }) => {
      const childElement = document.querySelector<HTMLElement>(child);
      const parentElement = document.querySelector<HTMLElement>(parent);
      if (!childElement || !parentElement) return 0;
      const childRect = childElement.getBoundingClientRect();
      const parentRect = parentElement.getBoundingClientRect();
      return Math.max(
        0,
        Math.min(childRect.bottom, parentRect.bottom, window.innerHeight) -
          Math.max(childRect.top, parentRect.top, 0),
      );
    },
    { child: childSelector, parent: parentSelector },
  );
}

test("844x390 PPT 工作台使用浏览器自然滚动", async ({ page }) => {
  await page.setViewportSize({ height: 390, width: 844 });
  await loginAsTeacher(page);
  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-pages");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-pages`);
  const heading = page.getByRole("heading", { name: "认识百分数 · 7 页" });
  await expect(heading).toBeVisible();

  const dimensions = await page.evaluate(() => ({
    clientHeight: document.documentElement.clientHeight,
    scrollHeight: document.documentElement.scrollHeight,
  }));
  expect(dimensions.scrollHeight).toBeGreaterThan(dimensions.clientHeight);

  const headingBox = await heading.boundingBox();
  expect(headingBox).not.toBeNull();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.mouse.move(
    (headingBox?.x ?? 0) + 8,
    (headingBox?.y ?? 0) + Math.min(16, (headingBox?.height ?? 0) / 2),
  );
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.mouse.wheel(0, 2_000);
  await expect
    .poll(() =>
      page.evaluate(
        () => window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2,
      ),
    )
    .toBe(true);
  await expect(page.getByRole("button", { name: "选择其他页面" })).toBeInViewport();
});

const studios = [
  {
    downloadLabel: "下载这张图片",
    name: "图片",
    path: "/app/creation/images",
    startLabel: "开始创作图片",
  },
  {
    downloadLabel: "下载视频说明",
    name: "视频",
    path: "/app/creation/videos",
    startLabel: "开始创作视频",
  },
  {
    downloadLabel: "下载课件预览",
    name: "PPT",
    path: "/app/creation/presentations",
    startLabel: "开始制作 PPT",
  },
] as const;

for (const studio of studios) {
  test(`844x390 ${studio.name}创作台保留足够结果空间且主要操作可下滑到达`, async ({ page }) => {
    await page.setViewportSize({ height: 390, width: 844 });
    await loginAsTeacher(page);
    await page.goto(studio.path);
    await page.getByRole("button", { name: studio.startLabel }).click();
    await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();

    const regions = await page.evaluate(() => {
      const main = document.querySelector<HTMLElement>('[data-testid="creation-studio"] > main');
      const composer = document.querySelector<HTMLElement>('[data-testid="creation-composer"]');
      if (!main || !composer) return null;
      const mainRect = main.getBoundingClientRect();
      const composerRect = composer.getBoundingClientRect();
      return {
        composerTop: composerRect.top,
        mainBottom: mainRect.bottom,
        mainClientHeight: main.clientHeight,
        mainScrollHeight: main.scrollHeight,
      };
    });
    expect(regions).not.toBeNull();
    expect(regions?.mainClientHeight ?? 0).toBeGreaterThanOrEqual(180);
    expect(regions?.mainScrollHeight ?? 0).toBeGreaterThan(regions?.mainClientHeight ?? 0);
    expect(regions?.mainBottom ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(
      (regions?.composerTop ?? 0) + 1,
    );
    expect(
      await visibleHeightWithin(
        page,
        '[data-testid="creation-main-visual"]',
        '[data-testid="creation-studio"] > main',
      ),
    ).toBeGreaterThanOrEqual(120);

    const main = page.locator('[data-testid="creation-studio"] > main');
    await main.hover();
    await page.mouse.wheel(0, 2_000);
    await expect
      .poll(() =>
        main.evaluate(
          (element) => element.scrollTop + element.clientHeight >= element.scrollHeight - 2,
        ),
      )
      .toBe(true);
    await expect(page.getByRole("button", { name: studio.downloadLabel })).toBeInViewport();
    await expect(page.getByRole("button", { name: "就用这张" })).toBeInViewport();
  });
}

test("1024x600 课堂导入摘要滚动后不被两层顶栏遮挡", async ({ page }) => {
  await page.setViewportSize({ height: 600, width: 1024 });
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/intro-options`);
  const heading = page.getByRole("heading", { name: "课堂导入设计" });
  await expect(heading).toBeVisible();
  const summary = page.getByTestId("intro-selected-summary");
  await expect(summary).toBeVisible();

  const headingBox = await heading.boundingBox();
  expect(headingBox).not.toBeNull();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.mouse.move((headingBox?.x ?? 0) + 8, (headingBox?.y ?? 0) + 12);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.mouse.wheel(0, 600);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);

  const summaryBox = await summary.boundingBox();
  expect(summaryBox?.y ?? 0).toBeGreaterThanOrEqual(111);
  await expect(page.getByRole("button", { name: "编辑当前方案" })).toBeInViewport();
});

test("1440x600 课堂导入详情滚动后保持在工作台顶栏下方", async ({ page }) => {
  await page.setViewportSize({ height: 600, width: 1440 });
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/intro-options`);
  const heading = page.getByRole("heading", { name: "课堂导入设计" });
  await expect(heading).toBeVisible();
  const details = page.getByTestId("intro-details-panel");
  await expect(details).toBeVisible();

  const headingBox = await heading.boundingBox();
  expect(headingBox).not.toBeNull();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.mouse.move((headingBox?.x ?? 0) + 8, (headingBox?.y ?? 0) + 12);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.mouse.wheel(0, 600);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);

  const detailsBox = await details.boundingBox();
  expect(detailsBox?.y ?? 0).toBeGreaterThanOrEqual(123);
  await expect(details.getByRole("button", { name: "编辑方案" })).toBeInViewport();
});

test("844x390 创作参数与画面细节保持互斥", async ({ page }) => {
  await page.setViewportSize({ height: 390, width: 844 });
  await loginAsTeacher(page);
  await page.goto("/app/creation/videos");

  await page.getByRole("button", { name: "调整创作参数" }).click();
  await expect(page.getByTestId("creation-parameter-bar")).toBeVisible();
  await page.getByRole("button", { name: "画面细节" }).click();
  await expect(page.getByRole("button", { name: "关闭画面细节" })).toBeVisible();
  await expect(page.getByTestId("creation-parameter-bar")).not.toBeVisible();

  await page.getByRole("button", { name: "调整创作参数" }).click();
  await expect(page.getByRole("button", { name: "关闭画面细节" })).not.toBeVisible();
  await expect(page.getByTestId("creation-parameter-bar")).toBeVisible();
});

test("1024x768 创作结果和采用操作首屏同时可见", async ({ page }) => {
  await page.setViewportSize({ height: 768, width: 1024 });
  await loginAsTeacher(page);
  await page.goto("/app/creation/videos");
  await page.getByRole("button", { name: "开始创作视频" }).click();
  await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();

  await expect(page.getByTestId("creation-main-visual")).toBeInViewport();
  await expect(page.getByRole("button", { name: "下载视频说明" })).toBeInViewport();
  await expect(page.getByRole("button", { name: "就用这张" })).toBeInViewport();

  const mainDimensions = await page
    .locator('[data-testid="creation-studio"] > main')
    .evaluate((element) => ({
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }));
  expect(mainDimensions.scrollHeight).toBeLessThanOrEqual(mainDimensions.clientHeight + 1);
});

test("390x844 三类创作台均可通过窄屏滚轮到达采用操作", async ({ page }) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await loginAsTeacher(page);

  for (const studio of studios) {
    await page.goto(studio.path);
    await page.getByRole("button", { name: studio.startLabel }).click();
    await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible();
    const main = page.locator('[data-testid="creation-studio"] > main');
    const dimensions = await main.evaluate((element) => ({
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }));
    if (dimensions.scrollHeight > dimensions.clientHeight + 1) {
      await main.hover();
      await page.mouse.wheel(0, 2_000);
    }
    await expect(page.getByRole("button", { name: "就用这张" })).toBeInViewport();
  }
});
