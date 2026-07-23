import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e/real-api",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  forbidOnly: Boolean(process.env.CI),
  outputDir: "test-results/real-api",
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report/real-api" }]],
  use: {
    baseURL: "http://127.0.0.1:4177",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "corepack pnpm dev --host 127.0.0.1 --port 4177 --strictPort",
    env: {
      VITE_API_BASE_URL: "/api/v2",
      VITE_API_MODE: "real",
      VITE_REAL_API_PROXY_TARGET: "http://127.0.0.1:8000",
    },
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
    timeout: 120_000,
    url: "http://127.0.0.1:4177/login",
  },
  projects: [
    {
      name: "real-api-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
