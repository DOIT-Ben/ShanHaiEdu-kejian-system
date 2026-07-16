import { describe, expect, it } from "vitest";
import { computeBackoffDelay, SseParser, streamEventSchema, type SseMessage } from "./eventStream";

describe("SseParser", () => {
  it("解析完整事件（id/event/data）", () => {
    const parser = new SseParser();
    const messages: SseMessage[] = [];
    parser.feed('id: ev_1\nevent: task.updated\ndata: {"a":1}\n\n', (message) => messages.push(message));
    expect(messages).toHaveLength(1);
    expect(messages[0]).toEqual({ id: "ev_1", event: "task.updated", data: '{"a":1}' });
  });

  it("支持跨 chunk 的增量输入", () => {
    const parser = new SseParser();
    const messages: SseMessage[] = [];
    parser.feed("data: hel", (message) => messages.push(message));
    parser.feed("lo\n", (message) => messages.push(message));
    expect(messages).toHaveLength(0);
    parser.feed("\n", (message) => messages.push(message));
    expect(messages).toHaveLength(1);
    expect(messages[0].data).toBe("hello");
  });

  it("多行 data 以换行拼接", () => {
    const parser = new SseParser();
    const messages: SseMessage[] = [];
    parser.feed("data: line1\ndata: line2\n\n", (message) => messages.push(message));
    expect(messages[0].data).toBe("line1\nline2");
  });

  it("忽略注释心跳行", () => {
    const parser = new SseParser();
    const messages: SseMessage[] = [];
    parser.feed(": keep-alive\n\ndata: x\n\n", (message) => messages.push(message));
    expect(messages).toHaveLength(1);
    expect(messages[0].data).toBe("x");
  });

  it("支持 CRLF 行结束", () => {
    const parser = new SseParser();
    const messages: SseMessage[] = [];
    parser.feed("data: y\r\n\r\n", (message) => messages.push(message));
    expect(messages).toHaveLength(1);
    expect(messages[0].data).toBe("y");
  });
});

describe("computeBackoffDelay", () => {
  it("按预设阶梯退避并封顶 30s（首个失败 1s）", () => {
    expect(computeBackoffDelay(1)).toBe(1000);
    expect(computeBackoffDelay(2)).toBe(2000);
    expect(computeBackoffDelay(3)).toBe(4000);
    expect(computeBackoffDelay(4)).toBe(8000);
    expect(computeBackoffDelay(6)).toBe(30_000);
    expect(computeBackoffDelay(99)).toBe(30_000);
  });
  it("0 或负数按首档处理", () => {
    expect(computeBackoffDelay(0)).toBe(1000);
  });
});

describe("streamEventSchema", () => {
  it("校验合法事件并默认 payload", () => {
    const parsed = streamEventSchema.parse({
      event_id: "ev_1",
      event_type: "task.updated",
      occurred_at: "2026-07-16T08:00:00Z",
      project_id: "proj_1",
    });
    expect(parsed.payload).toEqual({});
  });
  it("缺少必填字段时报错", () => {
    expect(() => streamEventSchema.parse({ event_id: "ev_1" })).toThrow();
  });
});
