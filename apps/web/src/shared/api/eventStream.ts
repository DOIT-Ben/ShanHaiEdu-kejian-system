export type SseEventEnvelope = {
  event_id: string;
  sequence_no: number;
  event_type: string;
  occurred_at: string;
  project_id?: string | null;
  resource: { type: string; id: string };
  payload: Record<string, unknown>;
  request_id?: string | null;
};

export class SseStreamError extends Error {
  readonly code?: string;
  readonly status: number;

  constructor(status: number, code?: string) {
    super(code ? `SSE stream failed: ${code}` : `SSE stream failed: ${String(status)}`);
    this.name = "SseStreamError";
    this.code = code;
    this.status = status;
  }
}

type StreamOptions = {
  fetchImpl?: typeof fetch;
  lastSequence?: number;
  onEvent: (event: SseEventEnvelope) => void;
  signal?: AbortSignal;
  url: string;
};

function isPositiveSequence(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function parseEnvelope(block: string): SseEventEnvelope | null {
  let id = "";
  let eventType = "message";
  const data: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    const value = separator === -1 ? "" : line.slice(separator + 1).replace(/^ /, "");
    if (field === "id") id = value;
    else if (field === "event") eventType = value || "message";
    else if (field === "data") data.push(value);
  }
  if (data.length === 0) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(data.join("\n")) as unknown;
  } catch {
    throw new SseStreamError(200, "INVALID_SSE_EVENT");
  }
  if (!parsed || typeof parsed !== "object") {
    throw new SseStreamError(200, "INVALID_SSE_EVENT");
  }
  const candidate = parsed as Partial<SseEventEnvelope>;
  const resource = candidate.resource;
  if (
    typeof candidate.event_id !== "string" ||
    !isPositiveSequence(candidate.sequence_no) ||
    typeof candidate.event_type !== "string" ||
    !/^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$/.test(candidate.event_type) ||
    typeof candidate.occurred_at !== "string" ||
    !resource ||
    typeof resource !== "object" ||
    Array.isArray(resource) ||
    typeof resource.type !== "string" ||
    typeof resource.id !== "string" ||
    !candidate.payload ||
    typeof candidate.payload !== "object" ||
    Array.isArray(candidate.payload)
  ) {
    throw new SseStreamError(200, "INVALID_SSE_EVENT");
  }
  if (id !== String(candidate.sequence_no) || eventType !== candidate.event_type) {
    throw new SseStreamError(200, "INVALID_SSE_EVENT");
  }
  return candidate as SseEventEnvelope;
}

async function readErrorCode(response: Response) {
  try {
    const body = (await response.json()) as { error?: { code?: unknown } };
    return typeof body.error?.code === "string" ? body.error.code : undefined;
  } catch {
    return undefined;
  }
}

export async function streamSseEvents({
  fetchImpl = fetch,
  lastSequence,
  onEvent,
  signal,
  url,
}: StreamOptions) {
  const headers = new Headers({ Accept: "text/event-stream" });
  if (lastSequence !== undefined) headers.set("Last-Event-ID", String(lastSequence));
  const response = await fetchImpl(url, { credentials: "include", headers, signal });
  if (!response.ok || !response.body) {
    throw new SseStreamError(response.status, await readErrorCode(response));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const event = parseEnvelope(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        if (event) onEvent(event);
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    const finalEvent = parseEnvelope(buffer);
    if (finalEvent) onEvent(finalEvent);
  } finally {
    reader.releaseLock();
  }
}

type SubscriptionOptions = {
  clearCursor: () => void;
  connect: (
    cursor: number | undefined,
    onEvent: (event: SseEventEnvelope) => void,
    signal: AbortSignal,
  ) => Promise<void>;
  initialCursor?: number;
  onEvent: (event: SseEventEnvelope) => void;
  refreshSnapshot: () => Promise<void>;
  signal: AbortSignal;
  wait?: (delayMs: number, signal: AbortSignal) => Promise<boolean>;
  writeCursor: (sequence: number) => void;
};

const MAX_RETRY_DELAY_MS = 15_000;

function retryDelay(attempt: number) {
  return Math.min(1_000 * 2 ** Math.max(0, attempt - 1), MAX_RETRY_DELAY_MS);
}

function isAbort(reason: unknown, signal: AbortSignal) {
  return signal.aborted || (reason instanceof DOMException && reason.name === "AbortError");
}

function waitForRetry(delayMs: number, signal: AbortSignal) {
  return new Promise<boolean>((resolve) => {
    if (signal.aborted) {
      resolve(false);
      return;
    }
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve(true);
    }, delayMs);
    const onAbort = () => {
      clearTimeout(timer);
      resolve(false);
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

export async function runSseSubscription({
  clearCursor,
  connect,
  initialCursor,
  onEvent,
  refreshSnapshot,
  signal,
  wait = waitForRetry,
  writeCursor,
}: SubscriptionOptions) {
  let cursor = initialCursor;
  let failedAttempts = 0;
  while (!signal.aborted) {
    const connectionState = { receivedEvent: false };
    try {
      await connect(
        cursor,
        (event) => {
          if (cursor !== undefined && event.sequence_no <= cursor) return;
          cursor = event.sequence_no;
          writeCursor(event.sequence_no);
          connectionState.receivedEvent = true;
          onEvent(event);
        },
        signal,
      );
      failedAttempts = connectionState.receivedEvent ? 0 : failedAttempts + 1;
    } catch (reason) {
      if (isAbort(reason, signal)) return;
      if (reason instanceof SseStreamError && reason.code === "EVENT_HISTORY_EXPIRED") {
        cursor = undefined;
        clearCursor();
        await refreshSnapshot();
        failedAttempts = 0;
        continue;
      }
      failedAttempts += 1;
    }
    if (!(await wait(retryDelay(failedAttempts), signal))) return;
  }
}
