import { expect, test, type Locator, type Page, type TestInfo } from "@playwright/test";
import { loginAsTeacher } from "./support/auth";

const viewports = [
  { height: 760, width: 320 },
  { height: 820, width: 375 },
  { height: 844, width: 414 },
  { height: 900, width: 768 },
  { height: 900, width: 1280 },
] as const;

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000101";

type Bounds = {
  bottom: number;
  height: number;
  left: number;
  right: number;
  top: number;
  width: number;
};

async function waitForStablePage(page: Page) {
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0, { timeout: 15_000 });
  await page.evaluate(async () => {
    await document.fonts.ready;
    const images = Array.from(document.images).filter(
      (image) => image.getBoundingClientRect().width > 0,
    );
    await Promise.all(
      images.map(async (image) => {
        if (!image.complete) {
          await new Promise<void>((resolve) => {
            image.addEventListener("load", () => resolve(), { once: true });
            image.addEventListener("error", () => resolve(), { once: true });
          });
        }
        if (typeof image.decode === "function") {
          await image.decode().catch(() => undefined);
        }
      }),
    );
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
  });
}

async function assertPageFrame(page: Page) {
  const metrics = await page.evaluate(() => ({
    bodyScrollWidth: document.body.scrollWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    mainCount: document.querySelectorAll("main").length,
    overflowingElements: Array.from(document.querySelectorAll<HTMLElement>("*"))
      .filter((element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return (
          rect.width > 0 &&
          rect.height > 0 &&
          style.display !== "none" &&
          (rect.left < -1 || rect.right > document.documentElement.clientWidth + 1)
        );
      })
      .slice(0, 12)
      .map((element) => ({
        className: typeof element.className === "string" ? element.className.slice(0, 160) : "",
        label: (element.getAttribute("aria-label") || element.textContent || "")
          .trim()
          .replace(/\s+/g, " ")
          .slice(0, 60),
        rect: {
          left: Math.round(element.getBoundingClientRect().left),
          right: Math.round(element.getBoundingClientRect().right),
          width: Math.round(element.getBoundingClientRect().width),
        },
        tag: element.tagName.toLowerCase(),
      })),
    viewportWidth: document.documentElement.clientWidth,
  }));
  expect(metrics.mainCount, "页面应只有一个主地标").toBe(1);
  expect(
    Math.max(metrics.bodyScrollWidth, metrics.documentScrollWidth),
    `页面横向溢出：${JSON.stringify(metrics, null, 2)}`,
  ).toBeLessThanOrEqual(metrics.viewportWidth + 1);
}

async function bounds(locator: Locator) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  return {
    bottom: (box?.y ?? 0) + (box?.height ?? 0),
    height: box?.height ?? 0,
    left: box?.x ?? 0,
    right: (box?.x ?? 0) + (box?.width ?? 0),
    top: box?.y ?? 0,
    width: box?.width ?? 0,
  } satisfies Bounds;
}

async function captureVisual(page: Page, testInfo: TestInfo, name: string) {
  await page.screenshot({
    animations: "disabled",
    caret: "hide",
    fullPage: true,
    path: testInfo.outputPath(`${name}.png`),
  });
  await expect(page).toHaveScreenshot(`${name}.png`, {
    animations: "disabled",
    caret: "hide",
    fullPage: true,
    maxDiffPixelRatio: 0.012,
  });
}

test.beforeEach(async ({ page }, testInfo) => {
  // Visual baselines are intentionally Chromium-only; WebKit and Edge remain covered by smoke tests.
  test.skip(testInfo.project.name !== "chromium", "视觉基线只绑定 Chromium");
  await page.emulateMedia({ reducedMotion: "reduce" });
});

for (const viewport of viewports) {
  const widthLabel = String(viewport.width);

  test(`首页 ${widthLabel}px 任务顺序与横向边界`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    await loginAsTeacher(page);
    await page.goto("/app");
    await waitForStablePage(page);

    await expect(page.getByRole("heading", { level: 1, name: "认识百分数" })).toBeVisible();
    const hero = await bounds(page.locator('section[aria-labelledby="home-brand-title"]'));
    const next = await bounds(page.locator('section[aria-labelledby="next-action-title"]'));
    const attention = await bounds(page.locator('section[aria-labelledby="attention-title"]'));
    const continuation = await bounds(page.locator('section[aria-labelledby="continue-title"]'));
    const recent = await bounds(page.locator('section[aria-labelledby="recent-results-title"]'));
    expect(hero.bottom).toBeLessThanOrEqual(next.top + 1);
    expect(next.top).toBeLessThanOrEqual(attention.top + 1);
    expect(continuation.top).toBeGreaterThanOrEqual(Math.max(next.bottom, attention.bottom) - 1);
    expect(recent.top).toBeGreaterThanOrEqual(continuation.bottom - 1);
    await assertPageFrame(page);
    await captureVisual(page, testInfo, `home-${widthLabel}`);
  });

  test(`项目列表 ${widthLabel}px 可扫描且无页面溢出`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    await loginAsTeacher(page);
    await page.goto("/app/projects");
    await expect(page.getByRole("heading", { level: 1, name: "我的项目" })).toBeVisible();
    await expect(page.getByRole("searchbox", { name: "搜索项目" })).toBeVisible();
    const list = page.getByRole("list");
    await expect(list).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("project-row").first()).toBeVisible({ timeout: 15_000 });
    const listBox = await bounds(list);
    expect(listBox.width).toBeLessThanOrEqual(viewport.width + 1);
    await assertPageFrame(page);
    await captureVisual(page, testInfo, `projects-${widthLabel}`);
  });

  test(`课时工作台 ${widthLabel}px 保留项目课时上下文`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    await loginAsTeacher(page);
    await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan`);
    await expect(page.getByRole("heading", { name: "百分数的意义" }).first()).toBeVisible();
    const header = page.locator('[data-testid="project-workbench"] > header');
    await expect(header).toContainText("认识百分数");
    await expect(header).toContainText("第 1 课时");
    await expect(header).toContainText("编写并确认教案");
    if (viewport.width <= 414) {
      await expect(page.getByRole("button", { name: "打开课时流程" })).toBeVisible();
    }
    await assertPageFrame(page);
    await captureVisual(page, testInfo, `workbench-${widthLabel}`);
  });

  test(`创作台 ${widthLabel}px 主画布与底部输入区不互相遮挡`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    await loginAsTeacher(page);
    await page.goto("/app/creation/images");
    await expect(page.getByRole("heading", { level: 1, name: "图片创作台" })).toBeVisible();
    await page.getByRole("button", { name: "开始创作图片" }).click();
    const output = page.getByRole("region", { name: "创作结果" });
    await expect(output).toHaveAttribute("aria-busy", "true");
    await captureVisual(page, testInfo, `creation-${widthLabel}-running`);
    await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible({ timeout: 10_000 });
    await waitForStablePage(page);

    const studio = await bounds(page.getByTestId("creation-studio"));
    const workArea = await bounds(page.getByRole("region", { name: "创作工作区" }));
    const composer = await bounds(page.getByTestId("creation-composer-panel"));
    const visual = await bounds(page.getByTestId("creation-main-visual"));
    expect(composer.bottom).toBeLessThanOrEqual(viewport.height + 1);
    expect(workArea.bottom).toBeLessThanOrEqual(composer.top + 1);
    expect(studio.bottom).toBeLessThanOrEqual(viewport.height + 1);
    if (viewport.width < 768) {
      expect(visual.width).toBeLessThanOrEqual(Math.min(360, viewport.width - 24) + 1);
      expect(visual.width).toBeGreaterThan(0);
      await expect(page.getByRole("button", { name: "创作设置" })).toContainText("课堂插画");
      await expect(page.getByRole("button", { name: "创作设置" })).toContainText("1:1");
    } else {
      expect(visual.width).toBeGreaterThanOrEqual(480);
      expect(visual.width).toBeLessThanOrEqual(720);
    }
    await assertPageFrame(page);
    await captureVisual(page, testInfo, `creation-${widthLabel}-ready`);
  });
}

test("创作台选中并保存状态具备可追踪反馈", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await loginAsTeacher(page);
  await page.goto("/app/creation/images");
  await page.getByRole("button", { name: "开始创作图片" }).click();
  await expect(page.getByRole("button", { name: "就用这张" })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "就用这张" }).click();
  await expect(page.getByRole("button", { name: "保存到项目" })).toBeVisible();
  await captureVisual(page, testInfo, "creation-1280-selected");
  await page.getByRole("button", { name: "保存到项目" }).click();
  const dialog = page.getByRole("dialog", { name: "保存到项目" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "保存到这个位置" }).click();
  await expect(page.getByText(/已放进“/)).toBeVisible();
  await captureVisual(page, testInfo, "creation-1280-saved");
});

test("项目列表搜索无结果时保持清晰空态", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await loginAsTeacher(page);
  await page.goto("/app/projects");
  await page.getByRole("searchbox", { name: "搜索项目" }).fill("不存在的课堂项目");
  await expect(page.getByText("没有找到匹配的项目，请调整搜索词。", { exact: true })).toBeVisible();
  await assertPageFrame(page);
  await captureVisual(page, testInfo, "projects-1280-empty");
});

test("项目列表服务异常时保留可读错误反馈", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await loginAsTeacher(page);
  await page.evaluate(() => {
    const future = Date.now() + 60_000;
    const originalFetch = window.fetch.bind(window);
    Date.now = () => future;
    window.fetch = (input, init) => {
      const url = String(
        typeof input === "string" ? input : input instanceof Request ? input.url : input,
      );
      if (url.includes("/api/v2/projects")) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: "temporary failure" }), {
            headers: { "Content-Type": "application/json" },
            status: 500,
          }),
        );
      }
      return originalFetch(input, init);
    };
  });
  await page.getByRole("link", { name: "项目", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/projects$/);
  await expect(
    page.getByText("项目列表暂时无法加载，请检查网络后重试。", { exact: true }),
  ).toBeVisible({
    timeout: 15_000,
  });
  await assertPageFrame(page);
  await captureVisual(page, testInfo, "projects-1280-error");
});
