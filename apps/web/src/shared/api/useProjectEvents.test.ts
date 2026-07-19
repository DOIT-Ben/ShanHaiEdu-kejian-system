import { describe, expect, it, vi } from "vitest";
import {
  createRefreshThrottle,
  readProjectLastEventId,
  streamProjectEvents,
} from "@/shared/api/useProjectEvents";

describe("project event transport", () => {
  it("restores Last-Event-ID through the OpenAPI-defined request header", async () => {
    sessionStorage.setItem("shanhaiedu.events.project-1.last-id", "event-41");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("id: event-42\nevent: task.updated\ndata: {}\n\n", {
        headers: { "Content-Type": "text/event-stream" },
        status: 200,
      }),
    );
    const onEvent = vi.fn();

    await streamProjectEvents({
      fetchImpl: fetchMock,
      lastEventId: readProjectLastEventId("project-1"),
      onEvent,
      projectId: "project-1",
    });

    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(request.headers).get("Last-Event-ID")).toBe("event-41");
    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({ id: "event-42", type: "task.updated" }),
    );
  });

  it("coalesces repeated connection errors into one snapshot refresh", () => {
    vi.useFakeTimers();
    const refresh = vi.fn();
    const throttle = createRefreshThrottle(refresh, 1_000);

    throttle.request();
    throttle.request();
    throttle.request();
    vi.advanceTimersByTime(1_000);

    expect(refresh).toHaveBeenCalledTimes(1);
    throttle.cancel();
    vi.useRealTimers();
  });
});
