import { describe, expect, it, vi } from "vitest";
import canonicalJobProgressEvent from "../../../../../contracts/fixtures/stage0/job-progress-event.json";
import { runSseSubscription, SseStreamError, streamSseEvents } from "@/shared/api/eventStream";

function sseResponse(event: Record<string, unknown>) {
  const sequence = String(event.sequence_no);
  const eventType = String(event.event_type);
  return new Response(`id: ${sequence}\nevent: ${eventType}\ndata: ${JSON.stringify(event)}\n\n`, {
    headers: { "Content-Type": "text/event-stream" },
    status: 200,
  });
}

describe("SSE event contract", () => {
  it("consumes the canonical stage-zero event fixture", async () => {
    const onEvent = vi.fn();

    await streamSseEvents({
      fetchImpl: vi.fn().mockResolvedValue(sseResponse(canonicalJobProgressEvent)),
      onEvent,
      url: "/events/stream",
    });

    expect(onEvent).toHaveBeenCalledWith(canonicalJobProgressEvent);
  });

  it("rejects an envelope that violates the canonical UUID format", async () => {
    const invalidEvent = { ...canonicalJobProgressEvent, event_id: "evt-not-a-uuid" };

    await expect(
      streamSseEvents({
        fetchImpl: vi.fn().mockResolvedValue(sseResponse(invalidEvent)),
        onEvent: vi.fn(),
        url: "/events/stream",
      }),
    ).rejects.toMatchObject({ code: "INVALID_SSE_EVENT", status: 200 });
  });
});

describe("SSE reconnect policy", () => {
  function subscriptionOptions({
    connect,
    signal,
    wait,
  }: {
    connect: () => Promise<void>;
    signal: AbortSignal;
    wait: (delay: number, signal: AbortSignal) => Promise<boolean>;
  }) {
    return {
      clearCursor: vi.fn(),
      connect,
      onEvent: vi.fn(),
      refreshSnapshot: vi.fn().mockResolvedValue(undefined),
      signal,
      wait,
      writeCursor: vi.fn(),
    };
  }

  it.each([401, 403, 404, 409, 422])("stops and reports permanent HTTP %s", async (status) => {
    const controller = new AbortController();
    const wait = vi.fn().mockResolvedValue(true);
    const failure = new SseStreamError(status, `HTTP_${String(status)}`);
    const connect = vi.fn().mockRejectedValue(failure);

    await expect(
      runSseSubscription(subscriptionOptions({ connect, signal: controller.signal, wait })),
    ).rejects.toBe(failure);
    expect(connect).toHaveBeenCalledOnce();
    expect(wait).not.toHaveBeenCalled();
  });

  it.each([408, 429, 500, 503])("retries transient HTTP %s", async (status) => {
    const controller = new AbortController();
    const wait = vi.fn().mockImplementation(() => {
      controller.abort();
      return Promise.resolve(false);
    });
    const connect = vi.fn().mockRejectedValue(new SseStreamError(status, `HTTP_${String(status)}`));

    await runSseSubscription(subscriptionOptions({ connect, signal: controller.signal, wait }));
    expect(connect).toHaveBeenCalledOnce();
    expect(wait).toHaveBeenCalledWith(1_000, controller.signal);
  });
});
