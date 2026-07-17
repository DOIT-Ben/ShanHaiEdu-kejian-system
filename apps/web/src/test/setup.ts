import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll, beforeEach } from "vitest";
import { server } from "@/mocks/server";
import { seedDb } from "@/mocks/seed";
import { db } from "@/mocks/db";
import { clearAllTimers } from "@/mocks/engine";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

beforeEach(() => {
  seedDb();
  db.speedFactor = 0; // 测试中任务即时完成
});

afterEach(() => {
  server.resetHandlers();
  clearAllTimers();
});

afterAll(() => {
  server.close();
});

// jsdom 未实现的 API
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => undefined;
}
if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
