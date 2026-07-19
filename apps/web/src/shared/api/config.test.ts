import { describe, expect, it } from "vitest";
import { resolveApiMode } from "@/shared/api/config";

describe("API mode boundary", () => {
  it("开发模式只接受 mock 或 real", () => {
    expect(resolveApiMode(undefined, false)).toBe("mock");
    expect(resolveApiMode("mock", false)).toBe("mock");
    expect(resolveApiMode("real", false)).toBe("real");
    expect(() => resolveApiMode("production", false)).toThrow("VITE_API_MODE 只能是 mock 或 real");
  });

  it("生产模式强制 real，并拒绝误带 mock 配置", () => {
    expect(resolveApiMode(undefined, true)).toBe("real");
    expect(resolveApiMode("real", true)).toBe("real");
    expect(() => resolveApiMode("mock", true)).toThrow("生产构建只允许 VITE_API_MODE=real");
  });
});
