import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";
import { seedDb } from "./seed";
import { restorePersistedSession } from "./handlers/auth";
import { DEFAULT_SCENARIO_ID, scenarioById } from "./scenarios";

export const SCENARIO_STORAGE_KEY = "__shanhai_mock_scenario__";

/** 读取当前场景：URL ?scenario= 优先，其次 sessionStorage，默认多项目场景。 */
export function resolveActiveScenarioId(): string {
  if (typeof window === "undefined") return DEFAULT_SCENARIO_ID;
  const fromUrl = new URLSearchParams(window.location.search).get("scenario");
  if (fromUrl && scenarioById.has(fromUrl)) {
    sessionStorage.setItem(SCENARIO_STORAGE_KEY, fromUrl);
    return fromUrl;
  }
  const stored = sessionStorage.getItem(SCENARIO_STORAGE_KEY);
  if (stored && scenarioById.has(stored)) return stored;
  return DEFAULT_SCENARIO_ID;
}

export function setActiveScenario(scenarioId: string): void {
  sessionStorage.setItem(SCENARIO_STORAGE_KEY, scenarioId);
  const url = new URL(window.location.href);
  url.searchParams.delete("scenario");
  window.location.href = url.toString();
}

export const worker = setupWorker(...handlers);

export async function startMockWorker(): Promise<string> {
  const scenarioId = resolveActiveScenarioId();
  seedDb(scenarioId);
  restorePersistedSession();
  await worker.start({
    onUnhandledRequest: (request, print) => {
      if (new URL(request.url).pathname.startsWith("/api/")) {
        print.warning();
      }
    },
    serviceWorker: { url: "/mockServiceWorker.js" },
  });
  return scenarioId;
}
