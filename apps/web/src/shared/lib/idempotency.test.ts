import { describe, expect, it } from "vitest";
import { createIdempotencyKey } from "./idempotency";

describe("createIdempotencyKey", () => {
  it("携带前缀且全局唯一", () => {
    const a = createIdempotencyKey("run");
    const b = createIdempotencyKey("run");
    expect(a).toMatch(/^run-/);
    expect(a).not.toBe(b);
  });
  it("默认前缀 web", () => {
    expect(createIdempotencyKey()).toMatch(/^web-/);
  });
});
