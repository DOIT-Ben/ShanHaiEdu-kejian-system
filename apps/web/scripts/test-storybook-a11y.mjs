import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import axe from "axe-core";
import { chromium } from "@playwright/test";

const host = "127.0.0.1";
const port = 6007;
const origin = `http://${host}:${String(port)}`;
const desktopViewport = { height: 900, name: "desktop-1440", width: 1440 };
const expectedCoreStoryCount = 94;
const expectedStoryCount = 126;
const coreViewports = [
  desktopViewport,
  { height: 768, name: "tablet-1024", width: 1024 },
  { height: 844, name: "narrow-390", width: 390 },
];
const forbiddenVisibleCopy = [
  { label: "内部调试词", pattern: /\b(?:debug|todo|mockruntime|usemockruntime|savemockdraft)\b/i },
  {
    label: "内部字段或路由键",
    pattern: /(?:future_widget|textbook\/source\.pdf|lesson[-_]plan|intro_options)/i,
  },
  { label: "内部制作标签", pattern: /(?:A版|B版|C版|信息饱满版|AI生成|生成器|验收)/ },
];
const viteCli = fileURLToPath(new URL("../node_modules/vite/bin/vite.js", import.meta.url));
const server = spawn(
  process.execPath,
  [
    viteCli,
    "preview",
    "--outDir",
    "storybook-static",
    "--host",
    host,
    "--port",
    String(port),
    "--strictPort",
  ],
  { stdio: ["ignore", "pipe", "pipe"] },
);

let serverOutput = "";
server.stdout.on("data", (chunk) => {
  serverOutput += String(chunk);
});
server.stderr.on("data", (chunk) => {
  serverOutput += String(chunk);
});

async function waitForStoryIndex() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(`${origin}/index.json`);
      if (response.ok) return response.json();
    } catch {
      // Static server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Storybook static server did not start.\n${serverOutput}`);
}

let browser;
try {
  const index = await waitForStoryIndex();
  const allStories = Object.values(index.entries ?? {}).filter((entry) => entry.type === "story");
  const requestedStoryIds = new Set(
    (process.env.SHANHAIEDU_STORYBOOK_A11Y_IDS ?? "").split(",").filter(Boolean),
  );
  const stories =
    requestedStoryIds.size === 0
      ? allStories
      : allStories.filter((story) => requestedStoryIds.has(story.id));
  if (requestedStoryIds.size > 0 && stories.length !== requestedStoryIds.size) {
    throw new Error("One or more requested Storybook stories were not found.");
  }
  const coreStories = stories.filter((story) => story.tags?.includes("core-viewport"));
  if (
    requestedStoryIds.size === 0 &&
    (stories.length !== expectedStoryCount || coreStories.length !== expectedCoreStoryCount)
  ) {
    throw new Error(
      `Storybook inventory drifted: expected ${String(expectedStoryCount)} stories and ${String(expectedCoreStoryCount)} core stories, received ${String(stories.length)} and ${String(coreStories.length)}.`,
    );
  }
  if (requestedStoryIds.size === 0 && coreStories.length === 0) {
    throw new Error("Storybook index does not contain any core-viewport stories.");
  }
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const failures = [];
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => {
    pageErrors.push(error.message);
  });
  let checkCount = 0;
  for (const story of stories) {
    const viewports = story.tags?.includes("core-viewport") ? coreViewports : [desktopViewport];
    for (const viewport of viewports) {
      checkCount += 1;
      consoleErrors.length = 0;
      pageErrors.length = 0;
      await page.setViewportSize({ height: viewport.height, width: viewport.width });
      await page.goto(`${origin}/iframe.html?id=${encodeURIComponent(story.id)}&viewMode=story`, {
        waitUntil: "networkidle",
      });
      if (consoleErrors.length > 0 || pageErrors.length > 0) {
        failures.push({
          consoleErrors: consoleErrors.length > 0 ? [...consoleErrors] : undefined,
          id: story.id,
          pageErrors: pageErrors.length > 0 ? [...pageErrors] : undefined,
          viewport: viewport.name,
        });
        continue;
      }
      try {
        await page.waitForFunction(
          () =>
            document.body.classList.contains("sb-show-main") ||
            document.body.classList.contains("sb-show-errordisplay"),
          undefined,
          { timeout: 10_000 },
        );
      } catch (error) {
        failures.push({
          id: story.id,
          pageErrors: [`Storybook render did not settle: ${String(error)}`],
          viewport: viewport.name,
        });
        continue;
      }
      await page.evaluate(async () => {
        await document.fonts?.ready;
        await new Promise((resolve) => requestAnimationFrame(() => resolve()));
      });
      await page.addScriptTag({ content: axe.source });
      const [result, layout, renderState, visibleCopy] = await Promise.all([
        page.evaluate(async () =>
          window.axe.run(document, {
            runOnly: {
              type: "tag",
              values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
            },
          }),
        ),
        page.evaluate(() => {
          const root = document.documentElement;
          const body = document.body;
          const clientWidth = root.clientWidth;
          return {
            clientWidth,
            overflowingElements: Array.from(document.querySelectorAll("body *"))
              .flatMap((element) => {
                const rect = element.getBoundingClientRect();
                if (
                  rect.width === 0 ||
                  rect.height === 0 ||
                  (rect.left >= -1 && rect.right <= clientWidth + 1)
                ) {
                  return [];
                }
                return [
                  {
                    className: element.getAttribute("class") ?? undefined,
                    left: Math.round(rect.left),
                    right: Math.round(rect.right),
                    scrollWidth: element.scrollWidth,
                    tag: element.tagName.toLowerCase(),
                    text: element.textContent?.trim().slice(0, 80) || undefined,
                    width: Math.round(rect.width),
                  },
                ];
              })
              .slice(0, 12),
            scrollWidth: Math.max(root.scrollWidth, body.scrollWidth),
          };
        }),
        page.evaluate(() => {
          const root = document.querySelector("#storybook-root");
          const rootStyle = root ? getComputedStyle(root) : undefined;
          const errorDisplayVisible = document.body.classList.contains("sb-show-errordisplay");
          const visiblePortalSurface = Array.from(
            document.querySelectorAll('[role="dialog"], [role="alertdialog"]'),
          ).some((element) => {
            const style = getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return (
              !element.closest('[hidden], [aria-hidden="true"], [inert]') &&
              style.display !== "none" &&
              style.visibility !== "hidden" &&
              rect.width > 0 &&
              rect.height > 0
            );
          });
          const rootSuppressed =
            !!root &&
            (root.matches('[hidden], [aria-hidden="true"], [inert]') ||
              rootStyle?.display === "none" ||
              rootStyle?.visibility === "hidden");
          return {
            errorMessage: errorDisplayVisible
              ? document.querySelector("#error-message")?.textContent?.trim() ||
                "Storybook displayed its error shell."
              : undefined,
            rootEmpty: !root || (!root.firstElementChild && !root.textContent?.trim()),
            rootHidden: !root || (rootSuppressed && !visiblePortalSurface),
          };
        }),
        page.evaluate(() => document.body.innerText),
      ]);
      const exposedCopy = forbiddenVisibleCopy
        .filter(({ pattern }) => pattern.test(visibleCopy))
        .map(({ label }) => label);
      if (
        consoleErrors.length > 0 ||
        pageErrors.length > 0 ||
        result.violations.length > 0 ||
        layout.scrollWidth > layout.clientWidth + 1 ||
        renderState.errorMessage ||
        renderState.rootEmpty ||
        renderState.rootHidden ||
        exposedCopy.length > 0
      ) {
        failures.push({
          consoleErrors: consoleErrors.length > 0 ? [...consoleErrors] : undefined,
          exposedCopy: exposedCopy.length > 0 ? exposedCopy : undefined,
          id: story.id,
          overflow:
            layout.scrollWidth > layout.clientWidth + 1
              ? {
                  clientWidth: layout.clientWidth,
                  elements: layout.overflowingElements,
                  scrollWidth: layout.scrollWidth,
                }
              : undefined,
          pageErrors: pageErrors.length > 0 ? [...pageErrors] : undefined,
          renderError: renderState.errorMessage,
          rootEmpty: renderState.rootEmpty || undefined,
          rootHidden: renderState.rootHidden || undefined,
          viewport: viewport.name,
          violations: result.violations.map(({ id, impact, nodes }) => ({
            id,
            impact,
            nodes: nodes.slice(0, 8).map(({ failureSummary, html, target }) => ({
              failureSummary,
              html,
              target,
            })),
          })),
        });
      }
    }
  }
  if (failures.length > 0) {
    console.error(JSON.stringify(failures, null, 2));
    process.exitCode = 1;
  } else {
    console.log(
      `Storybook accessibility, overflow and visible-copy checks passed: ${String(checkCount)} checks across ${String(stories.length)} stories; ${String(coreStories.length)} core stories covered at 1440, 1024 and 390 widths.`,
    );
  }
} finally {
  await browser?.close();
  server.kill();
}
