import { describe, expect, it, vi } from "vitest";
import {
  clearProjectLastSequence,
  projectEventQueryKeys,
  readProjectLastSequence,
  streamProjectEvents,
} from "@/shared/api/useProjectEvents";
import { runSseSubscription, SseStreamError } from "@/shared/api/eventStream";

const projectEvent = {
  event_id: "01960000-0000-7000-8000-000000000901",
  sequence_no: 42,
  event_type: "task.updated",
  occurred_at: "2026-07-20T00:00:00Z",
  project_id: "01960000-0000-7000-8000-000000000001",
  resource: {
    type: "generation_job",
    id: "01960000-0000-7000-8000-000000000701",
  },
  payload: { status: "running" },
  request_id: null,
} as const;

describe("project event transport", () => {
  it("restores Last-Event-ID as the positive project sequence", async () => {
    sessionStorage.setItem("shanhaiedu.events.project.project-1.sequence", "41");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(`id: 42\nevent: task.updated\ndata: ${JSON.stringify(projectEvent)}\n\n`, {
        headers: { "Content-Type": "text/event-stream" },
        status: 200,
      }),
    );
    const onEvent = vi.fn();

    await streamProjectEvents({
      fetchImpl: fetchMock,
      lastSequence: readProjectLastSequence("project-1"),
      onEvent,
      projectId: "project-1",
    });

    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(request.headers).get("Last-Event-ID")).toBe("41");
    expect(onEvent).toHaveBeenCalledWith(projectEvent);
  });

  it("does not reuse legacy UUID event ids as sequence cursors", () => {
    sessionStorage.setItem("shanhaiedu.events.project.project-1.sequence", "event-41");

    expect(readProjectLastSequence("project-1")).toBeUndefined();
  });

  it("ignores heartbeat comments without moving the cursor or invalidating queries", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(": heartbeat\n\n", {
        headers: { "Content-Type": "text/event-stream" },
        status: 200,
      }),
    );
    const onEvent = vi.fn();

    await streamProjectEvents({ fetchImpl: fetchMock, onEvent, projectId: "project-1" });

    expect(onEvent).not.toHaveBeenCalled();
  });

  it("surfaces the history-expired error code from a 409 response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json(
        {
          error: {
            code: "EVENT_HISTORY_EXPIRED",
            message: "cursor expired",
            retryable: false,
          },
          request_id: "req-1",
        },
        { status: 409 },
      ),
    );

    await expect(
      streamProjectEvents({ fetchImpl: fetchMock, onEvent: vi.fn(), projectId: "project-1" }),
    ).rejects.toMatchObject({ code: "EVENT_HISTORY_EXPIRED", status: 409 });
  });

  it("clears an expired cursor, refreshes the REST snapshot, then reconnects without a cursor", async () => {
    const order: string[] = [];
    const controller = new AbortController();
    const connect = vi
      .fn()
      .mockImplementationOnce((cursor: number | undefined) => {
        order.push(`connect:${String(cursor)}`);
        return Promise.reject(new SseStreamError(409, "EVENT_HISTORY_EXPIRED"));
      })
      .mockImplementationOnce((cursor: number | undefined) => {
        order.push(`connect:${String(cursor)}`);
        controller.abort();
        return Promise.resolve();
      });

    await runSseSubscription({
      clearCursor: () => order.push("clear"),
      connect,
      initialCursor: 41,
      onEvent: vi.fn(),
      refreshSnapshot: () => {
        order.push("refresh");
        return Promise.resolve();
      },
      signal: controller.signal,
      wait: () => Promise.resolve(true),
      writeCursor: vi.fn(),
    });

    expect(order).toEqual(["connect:41", "clear", "refresh", "connect:undefined"]);
  });

  it("backs off repeated failures and stops cleanly when aborted", async () => {
    const controller = new AbortController();
    const delays: number[] = [];
    const connect = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockRejectedValueOnce(new Error("still offline"))
      .mockImplementationOnce(() => {
        controller.abort();
        return Promise.reject(new DOMException("aborted", "AbortError"));
      });

    await runSseSubscription({
      clearCursor: vi.fn(),
      connect,
      onEvent: vi.fn(),
      refreshSnapshot: () => Promise.resolve(),
      signal: controller.signal,
      wait: (delay) => {
        delays.push(delay);
        return Promise.resolve(true);
      },
      writeCursor: vi.fn(),
    });

    expect(delays).toEqual([1_000, 2_000]);
    expect(connect).toHaveBeenCalledTimes(3);
  });

  it("maps project events to exact affected query families", () => {
    expect(projectEventQueryKeys("project-1", projectEvent)).toEqual([
      ["generation-jobs", projectEvent.resource.id],
      ["tasks", "project-1"],
    ]);
  });

  it("removes the saved project sequence", () => {
    sessionStorage.setItem("shanhaiedu.events.project.project-1.sequence", "41");
    clearProjectLastSequence("project-1");
    expect(readProjectLastSequence("project-1")).toBeUndefined();
  });
});
