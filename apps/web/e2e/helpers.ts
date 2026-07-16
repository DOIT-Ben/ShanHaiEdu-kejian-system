import { test as base, expect, type Page } from "@playwright/test";

/**
 * E2E 共享工具：登录 + 场景切换。
 * Mock 场景通过 sessionStorage 键 __shanhai_mock_scenario__ 控制（与 src/mocks/browser.ts 一致）。
 */

export const SCENARIO_KEY = "__shanhai_mock_scenario__";

export async function useScenario(page: Page, scenarioId: string): Promise<void> {
  await page.addInitScript(
    ([key, id]) => {
      sessionStorage.setItem(key, id);
    },
    [SCENARIO_KEY, scenarioId] as const,
  );
}

export async function login(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel(/邮箱或工号/).fill("teacher@shanhai.edu");
  await page.getByLabel(/密码/).fill("demo1234");
  await page.getByRole("button", { name: "登录" }).click();
  await page.waitForURL("**/app**");
}

export const test = base;
export { expect };
