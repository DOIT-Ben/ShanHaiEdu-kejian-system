import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import sseEventSchema from "../../../../../contracts/sse-event.schema.json";

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

const validateSseEventEnvelope = addFormats(
  new Ajv2020({ strict: false }),
).compile<SseEventEnvelope>(sseEventSchema);

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
  for (const line of block.split(/\r\n|\r|\n/)) {
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
  if (!validateSseEventEnvelope(parsed) || !isPositiveSequence(parsed.sequence_no)) {
    throw new SseStreamError(200, "INVALID_SSE_EVENT");
  }
  const candidate = parsed;
  if (id !== String(candidate.sequence_no) || eventType !== candidate.event_type) {
    throw new SseStreamError(200, "INVALID_SSE_EVENT");
  }
  return candidate;
}

// A trailing CR is kept in the buffer until the next chunk confirms whether it
// is the first half of CRLF; this prevents a split CRLF from becoming a blank
// event boundary prematurely.
function lineEndingLength(buffer: string, index: number, streamEnded: boolean) {
  if (buffer[index] === "\n") return 1;
  if (buffer[index] !== "\r") return 0;
  if (index + 1 >= buffer.length) return streamEnded ? 1 : 0;
  return buffer[index + 1] === "\n" ? 2 : 1;
}

function findEventBoundary(buffer: string, streamEnded: boolean) {
  for (let index = 0; index < buffer.length; index += 1) {
    const firstLength = lineEndingLength(buffer, index, streamEnded);
    if (!firstLength) continue;
    const secondLength = lineEndingLength(buffer, index + firstLength, streamEnded);
    if (secondLength) return { index, length: firstLength + secondLength };
    index += firstLength - 1;
  }
  return undefined;
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
      buffer += decoder.decode(value, { stream: !done });
      let boundary = findEventBoundary(buffer, done);
      while (boundary) {
        const event = parseEnvelope(buffer.slice(0, boundary.index));
        buffer = buffer.slice(boundary.index + boundary.length);
        if (event) onEvent(event);
        boundary = findEventBoundary(buffer, done);
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

function isPermanentClientError(reason: unknown) {
  return (
    reason instanceof SseStreamError &&
    reason.status >= 400 &&
    reason.status < 500 &&
    reason.status !== 408 &&
    reason.status !== 429
  );
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

async function refreshExpiredSnapshot({
  clearCursor,
  refreshSnapshot,
  signal,
  wait,
}: Pick<SubscriptionOptions, "clearCursor" | "refreshSnapshot" | "signal"> & {
  wait: NonNullable<SubscriptionOptions["wait"]>;
}) {
  clearCursor();
  let failedAttempts = 0;
  while (!signal.aborted) {
    try {
      await refreshSnapshot();
      return true;
    } catch (reason) {
      if (isAbort(reason, signal)) return false;
      failedAttempts += 1;
      if (!(await wait(retryDelay(failedAttempts), signal))) return false;
    }
  }
  return false;
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
        if (!(await refreshExpiredSnapshot({ clearCursor, refreshSnapshot, signal, wait }))) return;
        failedAttempts = 0;
        continue;
      }
      if (isPermanentClientError(reason)) throw reason;
      failedAttempts += 1;
    }
    if (!(await wait(retryDelay(failedAttempts), signal))) return;
  }
}
