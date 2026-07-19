import { describe, expect, it, vi } from "vitest";
import canonicalJobProgressEvent from "../../../../../contracts/fixtures/stage0/job-progress-event.json";
import { streamSseEvents } from "@/shared/api/eventStream";

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
