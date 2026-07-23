import { expect, test } from "@playwright/test";

test("real API harness reaches FastAPI and the production login route", async ({ page }) => {
  const response = await page.request.get("/api/v2/health/live");
  expect(response.ok()).toBe(true);
  await expect(response.json()).resolves.toMatchObject({
    data: { status: "ok" },
  });

  await page.goto("/login");
  await expect(page).toHaveURL(/\/login$/);
});
