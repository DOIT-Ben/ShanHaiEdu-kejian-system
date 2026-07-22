import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import axe from "axe-core";
import { chromium } from "@playwright/test";

const host = "127.0.0.1";
const port = 6007;
const origin = `http://${host}:${String(port)}`;
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
  const stories = Object.values(index.entries ?? {}).filter((entry) => entry.type === "story");
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const failures = [];
  for (const story of stories) {
    await page.goto(`${origin}/iframe.html?id=${encodeURIComponent(story.id)}&viewMode=story`, {
      waitUntil: "networkidle",
    });
    await page.addScriptTag({ content: axe.source });
    const result = await page.evaluate(async () =>
      window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      }),
    );
    if (result.violations.length > 0) {
      failures.push({
        id: story.id,
        violations: result.violations.map(({ id, impact }) => ({ id, impact })),
      });
    }
  }
  if (failures.length > 0) {
    console.error(JSON.stringify(failures, null, 2));
    process.exitCode = 1;
  } else {
    console.log(`Storybook accessibility check passed for ${String(stories.length)} stories.`);
  }
} finally {
  await browser?.close();
  server.kill();
}
