import { expect, test, type Page, type TestInfo } from "@playwright/test";
import axe from "axe-core";
import { loginAsAdmin, loginAsTeacher } from "./support/auth";
import { unlockWorkbenchStep } from "./support/runtime";

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000101";
const runtimeErrors = new WeakMap<Page, string[]>();
const internalCopy =
  /\b(?:mock|debug|test|todo)\b|AI生成|生成器|验收|信息饱满版|(?:A|B|C)版|工具名|mockServiceWorker|setupWorker|后台任务|局部重试|上游内容|候选/i;

test.beforeEach(({ page }) => {
  const errors: string[] = [];
  runtimeErrors.set(page, errors);
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().startsWith("Failed to load resource")) {
      errors.push(message.text());
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 400 && !response.url().endsWith("/favicon.ico")) {
      errors.push(`${String(response.status())} ${response.url()}`);
    }
  });
});

async function waitForStablePage(page: Page, heading: string, readyText: string) {
  await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible();
  await expect(page.getByText(readyText, { exact: false }).first()).toBeVisible();
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
  await page.evaluate(async () => {
    await document.fonts.ready;
    const viewportImages = Array.from(document.images).filter((image) => {
      const rect = image.getBoundingClientRect();
      return (
        rect.width > 0 &&
        rect.height > 0 &&
        rect.bottom >= 0 &&
        rect.right >= 0 &&
        rect.top <= window.innerHeight &&
        rect.left <= window.innerWidth
      );
    });
    await Promise.all(
      viewportImages.map(async (image) => {
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
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
    });
  });
}

async function auditScrollableContent(page: Page) {
  const audit = await page.evaluate(() => {
    const elements = Array.from(document.querySelectorAll<HTMLElement>("*"));
    const visible = (element: HTMLElement) =>
      element.clientWidth > 0 &&
      element.clientHeight > 0 &&
      getComputedStyle(element).display !== "none";
    const unexpectedHorizontal = elements
      .filter(visible)
      .filter((element) => {
        const className = typeof element.className === "string" ? element.className : "";
        return /(?:^|\s)overflow-(?:y-)?auto(?:\s|$)/.test(className);
      })
      .filter((element) => element.scrollWidth > element.clientWidth + 1)
      .filter((element) => {
        const style = getComputedStyle(element);
        const className = typeof element.className === "string" ? element.className : "";
        const intentionallyScrollable = /(?:^|\s)overflow-(?:x-)?auto(?:\s|$)/.test(className);
        return !intentionallyScrollable && !["hidden", "clip", "scroll"].includes(style.overflowX);
      })
      .map((element) => ({
        className: typeof element.className === "string" ? element.className : "",
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
        tag: element.tagName.toLowerCase(),
      }));

    const unreachableVertical = elements
      .filter(visible)
      .filter((element) => {
        const className = typeof element.className === "string" ? element.className : "";
        return /(?:^|\s)overflow-(?:y-)?auto(?:\s|$)/.test(className);
      })
      .filter((element) => element.scrollHeight > element.clientHeight + 1)
      .flatMap((element) => {
        const initialTop = element.scrollTop;
        element.scrollTop = element.scrollHeight;
        const reachedBottom = element.scrollTop + element.clientHeight >= element.scrollHeight - 1;
        element.scrollTop = initialTop;
        return reachedBottom
          ? []
          : [
              {
                className: typeof element.className === "string" ? element.className : "",
                clientHeight: element.clientHeight,
                scrollHeight: element.scrollHeight,
                tag: element.tagName.toLowerCase(),
              },
            ];
      });

    return { unexpectedHorizontal, unreachableVertical };
  });

  expect(audit.unexpectedHorizontal).toEqual([]);
  expect(audit.unreachableVertical).toEqual([]);
}

async function auditSharedControlScale(page: Page) {
  const oversized = await page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLElement>('[data-slot="button"]'))
      .filter((element) => element.offsetWidth > 0 && element.offsetHeight > 0)
      .filter((element) => element.getBoundingClientRect().height > 48)
      .map((element) => ({
        height: Math.round(element.getBoundingClientRect().height),
        label: element.getAttribute("aria-label") ?? element.textContent.trim().slice(0, 40),
      })),
  );
  expect(oversized).toEqual([]);
}

async function auditAccessibility(page: Page, selector?: string) {
  await page.addScriptTag({ content: axe.source });
  const violations = await page.evaluate(async (contextSelector) => {
    const context = contextSelector ? document.querySelector(contextSelector) : document;
    if (!context) throw new Error(`找不到无障碍审查区域：${contextSelector ?? "document"}`);
    const results = await (window as typeof window & { axe: typeof axe }).axe.run(context, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
    });
    return results.violations.map((violation) => ({
      help: violation.help,
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.map((node) => node.html),
    }));
  }, selector);

  expect(violations, `axe WCAG 2A/AA violations:\n${JSON.stringify(violations, null, 2)}`).toEqual(
    [],
  );
}

async function captureVisiblePage(
  page: Page,
  testInfo: TestInfo,
  name: string,
  heading: string,
  readyText: string,
) {
  await waitForStablePage(page, heading, readyText);
  await expect(page.locator("body")).not.toContainText(internalCopy);
  const viewportWidth = await page.evaluate(() => document.documentElement.clientWidth);
  const contentWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(contentWidth).toBeLessThanOrEqual(viewportWidth + 1);
  await auditScrollableContent(page);
  await auditSharedControlScale(page);
  await auditAccessibility(page);
  expect(runtimeErrors.get(page) ?? []).toEqual([]);
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: testInfo.outputPath(`${name}.png`),
  });
}

test("1440 首页无横向溢出且用户文案纯净", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await loginAsTeacher(page);
  await page.goto("/app");
  await captureVisiblePage(
    page,
    testInfo,
    "home-1440",
    "从一份教材，到一节孩子愿意听的好课",
    "继续当前课件",
  );
  await expect(page.getByRole("heading", { name: "也可以直接创作一件作品" })).toBeInViewport();
});

test("1024 品牌首页保持单主轴且无横向溢出", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 768, width: 1024 });
  await loginAsTeacher(page);
  await page.goto("/app");
  await captureVisiblePage(
    page,
    testInfo,
    "home-1024",
    "从一份教材，到一节孩子愿意听的好课",
    "继续当前课件",
  );
  await expect(page.getByLabel("创作向导")).toHaveCount(0);
  const heroPreview = await page.getByTestId("brand-hero-preview").boundingBox();
  expect(heroPreview?.width ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(560);
  expect(heroPreview?.height ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(300);
  const verticalFit = await page.evaluate(() => ({
    clientHeight: document.documentElement.clientHeight,
    scrollHeight: document.documentElement.scrollHeight,
  }));
  expect(verticalFit.scrollHeight).toBeLessThanOrEqual(verticalFit.clientHeight + 1);
  await expect(page.getByRole("heading", { name: "也可以直接创作一件作品" })).toBeInViewport();
});

test("390 品牌首页按任务顺序自然下滑", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await loginAsTeacher(page);
  await page.goto("/app");
  await captureVisiblePage(
    page,
    testInfo,
    "home-390",
    "从一份教材，到一节孩子愿意听的好课",
    "继续当前课件",
  );
  await expect(page.getByLabel("创作向导")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "继续完成这节课" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "也可以直接创作一件作品" })).toBeVisible();
});

test("1280 项目总览无横向溢出且用户文案纯净", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 900, width: 1280 });
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}`);
  await captureVisiblePage(page, testInfo, "project-1280", "认识百分数", "项目任务");
});

test("1024 教材与课时无横向溢出且用户文案纯净", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 900, width: 1024 });
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/materials`);
  await captureVisiblePage(page, testInfo, "materials-1024", "教材与课时", "安排课时");
});

test("390 教材文件名保持完整可辨认", async ({ page }) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/materials`);
  await waitForStablePage(page, "教材与课时", "安排课时");
  const fileName = page.getByRole("heading", { name: "百分数教材节选.pdf" });
  await expect(fileName).toBeVisible();
  await expect(fileName).toHaveAttribute("title", "百分数教材节选.pdf");
  expect(await fileName.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(
    true,
  );
  await auditScrollableContent(page);
});

test("390 课时工作台无横向溢出且用户文案纯净", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan`);
  await captureVisiblePage(page, testInfo, "lesson-plan-390", "百分数的意义", "教学内容");
  await page.evaluate(() => window.scrollTo({ top: 0 }));
  const heading = page
    .locator('[data-slot="page-header"]')
    .getByRole("heading", { exact: true, name: "百分数的意义" });
  const headingBox = await heading.boundingBox();
  expect(headingBox).not.toBeNull();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.mouse.move((headingBox?.x ?? 0) + 8, (headingBox?.y ?? 0) + 12);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.mouse.wheel(0, 4_000);
  await expect
    .poll(() =>
      page.evaluate(
        () => window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2,
      ),
    )
    .toBe(true);
  await expect(page.getByRole("heading", { name: "教学反思" })).toBeInViewport();
  await expect(page.locator("body")).not.toContainText(internalCopy);
  await auditScrollableContent(page);
  await auditAccessibility(page);
  expect(runtimeErrors.get(page) ?? []).toEqual([]);
  await page.screenshot({
    animations: "disabled",
    path: testInfo.outputPath("lesson-plan-390-bottom.png"),
  });
});

test("390 封面与视频备选保持紧凑且可横向选择", async ({ page }) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await loginAsTeacher(page);
  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-cover");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-cover`);
  const coverCandidate = page.getByRole("button", { name: "选择百格光窗" });
  await expect(coverCandidate).toBeVisible();
  await expect(page.getByText("3 张备选封面")).toBeVisible();
  expect(
    (await coverCandidate.boundingBox())?.width ?? Number.POSITIVE_INFINITY,
  ).toBeLessThanOrEqual(160);

  await unlockWorkbenchStep(page, projectId, lessonId, "video-style");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/video-style`);
  const styleCandidate = page.getByRole("button", { name: "选择纸艺微缩课堂" });
  await expect(styleCandidate).toBeVisible();
  expect(
    (await styleCandidate.boundingBox())?.width ?? Number.POSITIVE_INFINITY,
  ).toBeLessThanOrEqual(160);
  await auditScrollableContent(page);
  await auditAccessibility(page);
});

test("844×390 短屏核心预览保持可用尺寸", async ({ page }) => {
  await page.setViewportSize({ height: 390, width: 844 });
  await loginAsTeacher(page);

  await unlockWorkbenchStep(page, projectId, lessonId, "ppt-cover");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-cover`);
  const coverBox = await page.getByTestId("ppt-cover-preview").boundingBox();
  expect(coverBox?.width ?? 0).toBeGreaterThanOrEqual(240);
  expect(coverBox?.height ?? 0).toBeGreaterThanOrEqual(130);

  await unlockWorkbenchStep(page, projectId, lessonId, "video-style");
  await page.goto(`/app/projects/${projectId}/lessons/${lessonId}/work/video-style`);
  const styleBox = await page.getByTestId("video-style-preview").boundingBox();
  expect(styleBox?.width ?? 0).toBeGreaterThanOrEqual(240);
  expect(styleBox?.height ?? 0).toBeGreaterThanOrEqual(130);

  await page.goto("/app/creation/videos");
  const creationBox = await page.getByTestId("creation-main-visual").boundingBox();
  expect(creationBox?.width ?? 0).toBeGreaterThanOrEqual(220);
  expect(creationBox?.height ?? 0).toBeGreaterThanOrEqual(120);
});

test("390 核心页面优先展示下一步与可操作内容", async ({ page }) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await loginAsTeacher(page);

  await page.goto(`/app/projects/${projectId}/results`);
  await waitForStablePage(page, "素材与成果", "项目素材");
  const resultsSummary = page.getByTestId("results-summary");
  const currentVersion = page.getByTestId("current-result-summary");
  const firstAsset = page.getByRole("button", { name: /百格图里的 37%/ });
  expect((await resultsSummary.boundingBox())?.height ?? Number.POSITIVE_INFINITY).toBeLessThan(
    210,
  );
  expect((await currentVersion.boundingBox())?.height ?? Number.POSITIVE_INFINITY).toBeLessThan(
    190,
  );
  expect((await firstAsset.boundingBox())?.y ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(900);

  await page.goto("/app/creation/images");
  await waitForStablePage(page, "图片创作台", "画一张教学图片");
  await page.getByRole("button", { name: "调整模型、比例和画面细节" }).click();
  const parameterBar = page.getByTestId("creation-parameter-bar");
  expect(
    await parameterBar
      .locator('[role="combobox"]')
      .evaluateAll((controls) =>
        controls.slice(0, 4).map((control) => control.getAttribute("aria-label")),
      ),
  ).toEqual(["创作模型", "比例", "画面风格", "一次生成数量"]);
  await expect(page.getByTestId("creation-parameter-overflow-hint")).toBeVisible();

  await page.goto("/app/projects/new");
  await waitForStablePage(page, "从教材开始一套课堂作品", "项目信息");
  await expect(page.getByRole("combobox", { name: "年级" })).toHaveCount(1);
  await expect(page.getByRole("combobox", { name: "教材版本" })).toHaveCount(1);
  const nextStep = page.getByRole("button", { name: "下一步：上传教材" });
  await expect(nextStep).toBeVisible();
  await nextStep.click();
  await expect(page.getByRole("heading", { name: "教材文件" })).toBeInViewport();
});

test("390 活动导航与管理配置入口始终可见", async ({ page }) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/delivery`);
  const projectActive = page.getByRole("link", { name: "项目交付", exact: true });
  await expect(projectActive).toBeInViewport();

  await loginAsAdmin(page);
  await page.goto("/admin/audit");
  const adminActive = page.getByRole("link", { name: "审计记录", exact: true });
  await expect(adminActive).toBeInViewport();

  await page.goto("/admin/models");
  const configure = page.getByRole("button", { name: "配置文本生成" });
  await expect(configure).toBeInViewport();
  await configure.click();
  await expect(page.getByRole("heading", { name: "正在配置：文本生成" })).toBeVisible();
});

test("1024 通用创作中心无横向溢出且用户文案纯净", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 900, width: 1024 });
  await loginAsTeacher(page);
  await page.goto("/app/creation/images");
  await captureVisiblePage(page, testInfo, "creation-images-1024", "图片创作台", "画一张教学图片");
});

test("1024 创作中心最近作品保持紧凑", async ({ page }) => {
  await page.setViewportSize({ height: 900, width: 1024 });
  await loginAsTeacher(page);
  await page.goto("/app/creation");
  const recentPreview = await page.getByTestId("recent-primary-preview").boundingBox();
  expect(recentPreview?.width ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(260);
  expect(recentPreview?.height ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(260);
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollHeight: document.documentElement.scrollHeight,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
  expect(dimensions.scrollHeight).toBeLessThanOrEqual(1500);
});

test("1024 视频创作参数完整可达", async ({ page }) => {
  await page.setViewportSize({ height: 900, width: 1024 });
  await loginAsTeacher(page);
  await page.goto("/app/creation/videos");
  await waitForStablePage(page, "视频创作台", "完整要求");
  const fullPrompt = page.getByRole("button", { name: "查看完整创作要求" });
  await expect(fullPrompt).toBeInViewport();
  const fullPromptBox = await fullPrompt.boundingBox();
  expect((fullPromptBox?.x ?? 1024) + (fullPromptBox?.width ?? 0)).toBeLessThanOrEqual(1024);
});

test("1440 素材预览不随卡片无限放大", async ({ page }) => {
  await page.setViewportSize({ height: 900, width: 1440 });
  await loginAsTeacher(page);
  await page.goto(`/app/projects/${projectId}/results`);
  await waitForStablePage(page, "素材与成果", "项目素材");
  const previewHeights = await page
    .locator('[data-slot="artifact-preview"]')
    .evaluateAll((previews) => previews.map((preview) => preview.getBoundingClientRect().height));
  expect(previewHeights.length).toBeGreaterThan(1);
  previewHeights.forEach((height) => expect(height).toBeLessThanOrEqual(161));
  const mediaRatios = await page
    .locator('[data-slot="artifact-preview-media"]')
    .evaluateAll((previews) =>
      previews.map((preview) => ({
        actual: preview.getBoundingClientRect().width / preview.getBoundingClientRect().height,
        expected: preview.getAttribute("data-preview-ratio"),
      })),
    );
  const expectedRatios: Record<string, number> = { "1:1": 1, "4:3": 4 / 3, "16:9": 16 / 9 };
  mediaRatios.forEach(({ actual, expected }) => {
    const expectedRatio = expected ? expectedRatios[expected] : undefined;
    expect(expectedRatio).toBeDefined();
    expect(actual).toBeCloseTo(expectedRatio ?? 0, 1);
  });
});

test("1024 管理端无横向溢出且用户文案纯净", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 900, width: 1024 });
  await loginAsAdmin(page);
  await captureVisiblePage(page, testInfo, "admin-content-1024", "内容中心", "小学数学默认教案");
});

test("1024 教师端次级页面保持紧凑且无横向溢出", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 900, width: 1024 });
  await loginAsTeacher(page);
  const pages = [
    {
      heading: "素材与成果",
      name: "project-results-1024",
      path: `/app/projects/${projectId}/results`,
      readyText: "项目素材",
    },
    {
      heading: "项目交付",
      name: "project-delivery-1024",
      path: `/app/projects/${projectId}/delivery`,
      readyText: "交付门槛",
    },
    { heading: "任务中心", name: "tasks-1024", path: "/app/tasks", readyText: "进度更新" },
    {
      heading: "果汁标签侦探 · 视频图片资产",
      name: "creation-batch-1024",
      path: "/app/creation/batches/mock-batch",
      readyText: "保存到项目",
    },
  ];

  for (const entry of pages) {
    await page.goto(entry.path);
    await captureVisiblePage(page, testInfo, entry.name, entry.heading, entry.readyText);
  }
});

test("1024 管理端各页面保持紧凑且无横向溢出", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 900, width: 1024 });
  await loginAsAdmin(page);
  const pages = [
    {
      heading: "工作流",
      name: "admin-workflows-1024",
      path: "/admin/workflows",
      readyText: "保存草稿",
    },
    {
      heading: "模型服务",
      name: "admin-models-1024",
      path: "/admin/models",
      readyText: "添加模型服务",
    },
    {
      heading: "运行与费用",
      name: "admin-usage-1024",
      path: "/admin/usage",
      readyText: "当前积压",
    },
    { heading: "用户权限", name: "admin-users-1024", path: "/admin/users", readyText: "添加成员" },
    { heading: "审计记录", name: "admin-audit-1024", path: "/admin/audit", readyText: "导出记录" },
  ];

  for (const entry of pages) {
    await page.goto(entry.path);
    await captureVisiblePage(page, testInfo, entry.name, entry.heading, entry.readyText);
  }
});

test("1024 全局下拉框尺寸统一且弹层可读", async ({ page }, testInfo) => {
  await page.setViewportSize({ height: 900, width: 1024 });
  await loginAsTeacher(page);
  await page.goto("/app/projects/new");

  const grade = page.getByRole("combobox", { name: "年级" });
  const textbook = page.getByRole("combobox", { name: "教材版本" });
  for (const control of [grade, textbook]) {
    await expect(control).toBeVisible();
    expect((await control.boundingBox())?.height).toBe(40);
  }

  await grade.click();
  await expect(page.getByRole("option", { name: "六年级" })).toBeVisible();
  await expect(page.getByRole("option", { name: "一年级" })).toBeVisible();
  await page.screenshot({
    animations: "disabled",
    fullPage: true,
    path: testInfo.outputPath("select-open-1024.png"),
  });
  await auditAccessibility(page, '[role="listbox"]');
  await page.keyboard.press("Escape");
  await auditAccessibility(page);
});
