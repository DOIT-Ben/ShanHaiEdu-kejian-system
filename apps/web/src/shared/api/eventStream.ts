import { z } from "zod";

/**
 * SSE 事件通道（GET /api/v2/events?project_id=&last_event_id=）。
 * 事件只用于触发 TanStack Query 失效，不作为权威状态。
 * 断线指数退避重连并携带 Last-Event-ID；连续失败降级为轮询模式。
 */

export const streamEventSchema = z.object({
  event_id: z.string(),
  event_type: z.string(),
  occurred_at: z.string(),
  project_id: z.string(),
  organization_id: z.string().nullable().optional(),
  lesson_id: z.string().nullable().optional(),
  node_key: z.string().nullable().optional(),
  task_id: z.string().nullable().optional(),
  payload: z.record(z.string(), z.unknown()).optional().default({}),
});

export type StreamEvent = z.infer<typeof streamEventSchema>;

export type ConnectionMode = "connecting" | "sse" | "reconnecting" | "polling" | "offline";

export interface SseMessage {
  id?: string;
  event?: string;
  data: string;
}

/** 增量 SSE 文本解析器（可独立单测）。 */
export class SseParser {
  private buffer = "";
  private current: { id?: string; event?: string; data: string[] } = { data: [] };

  feed(chunk: string, onMessage: (message: SseMessage) => void): void {
    this.buffer += chunk;
    let newlineIndex = this.buffer.search(/\r?\n/);
    while (newlineIndex >= 0) {
      const line = this.buffer.slice(0, newlineIndex);
      this.buffer = this.buffer.slice(newlineIndex + (this.buffer[newlineIndex] === "\r" ? 2 : 1));
      this.processLine(line, onMessage);
      newlineIndex = this.buffer.search(/\r?\n/);
    }
  }

  private processLine(line: string, onMessage: (message: SseMessage) => void): void {
    if (line === "") {
      if (this.current.data.length > 0) {
        onMessage({
          id: this.current.id,
          event: this.current.event,
          data: this.current.data.join("\n"),
        });
      }
      this.current = { data: [] };
      return;
    }
    if (line.startsWith(":")) return; // 注释/心跳
    const colonIndex = line.indexOf(":");
    const field = colonIndex === -1 ? line : line.slice(0, colonIndex);
    let value = colonIndex === -1 ? "" : line.slice(colonIndex + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "data") this.current.data.push(value);
    else if (field === "id") this.current.id = value;
    else if (field === "event") this.current.event = value;
  }
}

const BACKOFF_STEPS_MS = [1000, 2000, 4000, 8000, 15000, 30000];
const POLLING_THRESHOLD = 4;

export function computeBackoffDelay(consecutiveFailures: number): number {
  const index = Math.min(Math.max(consecutiveFailures - 1, 0), BACKOFF_STEPS_MS.length - 1);
  return BACKOFF_STEPS_MS[index];
}

export interface EventStreamOptions {
  url: string;
  initialLastEventId?: string | null;
  onEvent: (event: StreamEvent) => void;
  onModeChange?: (mode: ConnectionMode) => void;
  /** 测试注入。 */
  fetchFn?: typeof fetch;
}

export interface EventStreamHandle {
  close: () => void;
  getLastEventId: () => string | null;
}

export function createEventStream(options: EventStreamOptions): EventStreamHandle {
  const fetchFn = options.fetchFn ?? fetch;
  let lastEventId: string | null = options.initialLastEventId ?? null;
  let closed = false;
  let failures = 0;
  let controller: AbortController | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const setMode = (mode: ConnectionMode) => {
    if (!closed) options.onModeChange?.(mode);
  };

  const scheduleReconnect = () => {
    if (closed) return;
    failures += 1;
    setMode(failures >= POLLING_THRESHOLD ? "polling" : "reconnecting");
    const delay = failures >= POLLING_THRESHOLD ? 30_000 : computeBackoffDelay(failures);
    reconnectTimer = setTimeout(() => {
      void connect();
    }, delay);
  };

  const connect = async () => {
    if (closed) return;
    controller = new AbortController();
    if (failures === 0) setMode("connecting");
    try {
      const target = new URL(options.url, typeof window !== "undefined" ? window.location.origin : "http://localhost");
      if (lastEventId) target.searchParams.set("last_event_id", lastEventId);
      const response = await fetchFn(target.toString(), {
        headers: {
          Accept: "text/event-stream",
          ...(lastEventId ? { "Last-Event-ID": lastEventId } : {}),
        },
        credentials: "include",
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`SSE 连接失败：HTTP ${response.status}`);
      }
      failures = 0;
      setMode("sse");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const parser = new SseParser();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        parser.feed(decoder.decode(value, { stream: true }), (message) => {
          if (message.id) lastEventId = message.id;
          try {
            const parsed = streamEventSchema.safeParse(JSON.parse(message.data));
            if (parsed.success) {
              if (!message.id) lastEventId = parsed.data.event_id;
              options.onEvent(parsed.data);
            }
          } catch {
            // 忽略无法解析的事件（保持通道健壮性）
          }
        });
      }
      // 服务端正常结束流，视为断线重连
      if (!closed) scheduleReconnect();
    } catch {
      if (!closed) scheduleReconnect();
    }
  };

  void connect();

  return {
    close: () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      controller?.abort();
      options.onModeChange?.("offline");
    },
    getLastEventId: () => lastEventId,
  };
}
