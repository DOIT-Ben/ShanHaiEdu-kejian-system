import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

function requiredEnvironment(name: string) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required for real API Playwright`);
  return value;
}

const repositoryRoot = fileURLToPath(new URL("../..", import.meta.url));
const webRoot = fileURLToPath(new URL(".", import.meta.url));
const webPort = Number.parseInt(process.env.SHANHAI_E2E_WEB_PORT ?? "44177", 10);
const apiPort = Number.parseInt(process.env.SHANHAI_E2E_API_PORT ?? "58080", 10);
const providerPort = Number.parseInt(process.env.SHANHAI_E2E_PROVIDER_PORT ?? "58081", 10);
const webOrigin = `http://127.0.0.1:${String(webPort)}`;
const apiOrigin = `http://127.0.0.1:${String(apiPort)}`;
const providerOrigin = `http://127.0.0.1:${String(providerPort)}`;

export default defineConfig({
  testDir: "./e2e/real-api",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  outputDir: "test-results/real-api",
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report/real-api" }]],
  use: {
    baseURL: webOrigin,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `uv run python -B tests/integration/r1_text_provider_stub.py --host 127.0.0.1 --port ${String(providerPort)}`,
      cwd: repositoryRoot,
      reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
      timeout: 120_000,
      url: `${providerOrigin}/health`,
    },
    {
      command: `uv run uvicorn apps.api.main:app --host 127.0.0.1 --port ${String(apiPort)} --no-proxy-headers`,
      cwd: repositoryRoot,
      env: {
        ...process.env,
        SHANHAI_DATABASE_URL: requiredEnvironment("SHANHAI_DATABASE_URL"),
        SHANHAI_ENVIRONMENT: "test",
        SHANHAI_OBJECT_STORAGE_ACCESS_KEY: requiredEnvironment("SHANHAI_OBJECT_STORAGE_ACCESS_KEY"),
        SHANHAI_OBJECT_STORAGE_ENDPOINT: requiredEnvironment("SHANHAI_OBJECT_STORAGE_ENDPOINT"),
        SHANHAI_OBJECT_STORAGE_HEALTH_URL: requiredEnvironment("SHANHAI_OBJECT_STORAGE_HEALTH_URL"),
        SHANHAI_OBJECT_STORAGE_SECRET_KEY: requiredEnvironment("SHANHAI_OBJECT_STORAGE_SECRET_KEY"),
        SHANHAI_OBJECT_STORAGE_SECURE: "false",
        SHANHAI_REDIS_URL: requiredEnvironment("SHANHAI_REDIS_URL"),
        SHANHAI_SESSION_ACCESS_CODE: requiredEnvironment("SHANHAI_SESSION_ACCESS_CODE"),
        SHANHAI_SESSION_ALLOWED_ORIGINS: JSON.stringify([webOrigin]),
        SHANHAI_SESSION_COOKIE_SECURE: "false",
        SHANHAI_SESSION_CSRF_SECRET: requiredEnvironment("SHANHAI_SESSION_CSRF_SECRET"),
        SHANHAI_SESSION_TEACHER_PRINCIPAL_ID: requiredEnvironment(
          "SHANHAI_SESSION_TEACHER_PRINCIPAL_ID",
        ),
        SHANHAI_SESSION_TRUSTED_PROXY_HOSTS: JSON.stringify(["127.0.0.1"]),
        SHANHAI_TEXT_PROVIDER_BASE_URL: `${providerOrigin}/v1`,
        SHANHAI_TEXT_PROVIDER_MODEL: "r1-deterministic-http-v1",
        SHANHAI_TEXT_PROVIDER_NAME: "r1-deterministic-http",
        SHANHAI_TEXT_PROVIDER_SECRET_ENV: "SHANHAI_E2E_TEXT_PROVIDER_KEY",
        SHANHAI_E2E_TEXT_PROVIDER_KEY: requiredEnvironment("SHANHAI_E2E_TEXT_PROVIDER_KEY"),
      },
      reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
      timeout: 120_000,
      url: `${apiOrigin}/health/live`,
    },
    {
      command: `corepack pnpm preview --host 127.0.0.1 --port ${String(webPort)} --strictPort`,
      cwd: webRoot,
      reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "1",
      timeout: 120_000,
      url: `${webOrigin}/login`,
    },
  ],
  projects: [{ name: "real-api-chromium", use: { ...devices["Desktop Chrome"] } }],
});
