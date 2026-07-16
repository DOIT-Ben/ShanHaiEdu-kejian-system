import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll, beforeEach } from "vitest";
import { cleanup } from "@testing-library/react";
import { server } from "@/mocks/server";
import { seedDb } from "@/mocks/seed";
import { clearAllTimers } from "@/mocks/engine";
import { clearSubscribers } from "@/mocks/events";
import { setCsrfToken } from "@/shared/api/client";

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

beforeEach(() => {
  // 每个用例独立种子（测试提速：任务时长 ×0.05）
  seedDb("projects.multiple", { speedFactor: 0.05 });
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
  clearAllTimers();
  clearSubscribers();
  setCsrfToken(null);
});

afterAll(() => {
  server.close();
});

// jsdom 缺失的浏览器 API
if (typeof window !== "undefined") {
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
  if (!window.ResizeObserver) {
    window.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => undefined;
  }
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
    Element.prototype.setPointerCapture = () => undefined;
    Element.prototype.releasePointerCapture = () => undefined;
  }
}
