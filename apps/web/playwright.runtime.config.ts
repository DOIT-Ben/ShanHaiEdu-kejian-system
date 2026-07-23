import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e/runtime",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  outputDir: "test-results/runtime",
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report/runtime" }]],
  use: {
    baseURL: "http://127.0.0.1:4176",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "corepack pnpm dev --host 127.0.0.1 --port 4176 --strictPort",
    env: {
      VITE_API_BASE_URL: "/api/v2",
      VITE_API_MODE: "real",
      VITE_RUNTIME_CONTRACT_TEST: "1",
    },
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
    timeout: 120_000,
    url: "http://127.0.0.1:4176/app",
  },
  projects: [{ name: "runtime-chromium", use: { ...devices["Desktop Chrome"] } }],
});
