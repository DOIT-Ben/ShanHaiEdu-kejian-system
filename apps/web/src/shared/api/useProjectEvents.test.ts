import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import {
  clearProjectLastSequence,
  invalidateProjectQueries,
  projectEventQueryKeys,
  readProjectLastSequence,
  streamProjectEvents,
  useProjectEvents,
} from "@/shared/api/useProjectEvents";
import { runSseSubscription, SseStreamError } from "@/shared/api/eventStream";

const projectEvent = {
  event_id: "01960000-0000-7000-8000-000000000901",
  sequence_no: 42,
  event_type: "generation.job.progress",
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
      new Response(
        `id: 42\nevent: generation.job.progress\ndata: ${JSON.stringify(projectEvent)}\n\n`,
        {
          headers: { "Content-Type": "text/event-stream" },
          status: 200,
        },
      ),
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

  it("parses CRLF event frames when a carriage return and line feed arrive in separate chunks", async () => {
    const encoder = new TextEncoder();
    const nextEvent = {
      ...projectEvent,
      event_id: "01960000-0000-7000-8000-000000000902",
      sequence_no: 43,
    };
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of [
          "id: 42\r",
          "\nevent: generation.job.progress\r",
          `\ndata: ${JSON.stringify(projectEvent)}\r`,
          "\n\r",
          "\nid: 43\r",
          "\nevent: generation.job.progress\r",
          `\ndata: ${JSON.stringify(nextEvent)}\r`,
          "\n\r",
          "\n",
        ]) {
          controller.enqueue(encoder.encode(chunk));
        }
        controller.close();
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(body, {
        headers: { "Content-Type": "text/event-stream" },
        status: 200,
      }),
    );
    const onEvent = vi.fn();

    await streamProjectEvents({ fetchImpl: fetchMock, onEvent, projectId: "project-1" });

    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent).toHaveBeenNthCalledWith(1, projectEvent);
    expect(onEvent).toHaveBeenNthCalledWith(2, nextEvent);
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

  it("backs off and retries the REST snapshot before reconnecting after history expires", async () => {
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
        return Promise.reject(new DOMException("aborted", "AbortError"));
      });
    const refreshSnapshot = vi
      .fn()
      .mockImplementationOnce(() => {
        order.push("refresh:failed-1");
        return Promise.reject(new Error("snapshot unavailable"));
      })
      .mockImplementationOnce(() => {
        order.push("refresh:failed-2");
        return Promise.reject(new Error("snapshot still unavailable"));
      })
      .mockImplementationOnce(() => {
        order.push("refresh:ready");
        return Promise.resolve();
      });

    await runSseSubscription({
      clearCursor: () => order.push("clear"),
      connect,
      initialCursor: 41,
      onEvent: vi.fn(),
      refreshSnapshot,
      signal: controller.signal,
      wait: (delay) => {
        order.push(`wait:${String(delay)}`);
        return Promise.resolve(true);
      },
      writeCursor: vi.fn(),
    });

    expect(order).toEqual([
      "connect:41",
      "clear",
      "refresh:failed-1",
      "wait:1000",
      "refresh:failed-2",
      "wait:2000",
      "refresh:ready",
      "connect:undefined",
    ]);
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
      ["projects", "project-1", "materials"],
    ]);

    const keysFor = (type: string, id = `${type}-1`) =>
      projectEventQueryKeys("project-1", {
        ...projectEvent,
        resource: { id, type },
      });
    expect(keysFor("automation_policy")).toEqual([["projects", "project-1", "automation-policy"]]);
    expect(keysFor("lesson_collection")).toEqual([
      ["projects", "project-1", "lessons"],
      ["lessons"],
      ["projects", "project-1"],
      ["projects"],
      ["projects", "project-1", "workflow"],
    ]);
    expect(keysFor("lesson", "lesson-1")).toEqual([
      ["projects", "project-1", "lessons"],
      ["lessons", "lesson-1"],
      ["projects", "project-1", "workflow"],
    ]);
    expect(keysFor("source_material", "material-1")).toEqual([
      ["projects", "project-1", "materials"],
      ["projects", "project-1", "materials", "material-1"],
      ["projects", "project-1", "materials", "material-1", "file-asset"],
      ["projects", "project-1", "materials", "material-1", "parse-versions"],
      ["projects", "project-1", "workflow"],
    ]);
    expect(keysFor("artifact", "artifact-1")).toEqual([
      ["artifacts", "artifact-1"],
      ["projects", "project-1", "artifacts"],
      ["projects", "project-1", "workflow"],
    ]);
    expect(keysFor("asset_binding", "binding-1")).toEqual([
      ["projects", "project-1", "asset-slots"],
      ["projects", "project-1", "asset-package"],
      ["projects", "project-1", "workflow"],
    ]);
    expect(keysFor("future_resource", "future-1")).toEqual([
      ["projects", "project-1"],
      ["projects"],
      ["projects", "project-1", "workflow"],
    ]);
  });

  it("invalidates every single-lesson cache after a collection event", async () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(["lessons", "lesson-1"], { title: "旧课时一" });
    queryClient.setQueryData(["lessons", "lesson-2"], { title: "旧课时二" });
    queryClient.setQueryData(["unrelated", "lesson-1"], { title: "不相关" });

    await invalidateProjectQueries(queryClient, "project-1", {
      ...projectEvent,
      resource: { id: "collection-1", type: "lesson_collection" },
    });

    expect(queryClient.getQueryState(["lessons", "lesson-1"])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(["lessons", "lesson-2"])?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(["unrelated", "lesson-1"])?.isInvalidated).toBe(false);
  });

  it("invalidates the combined material details cache after a source material event", async () => {
    const queryClient = new QueryClient();
    const materialKey = ["projects", "project-1", "materials", "material-1"] as const;
    queryClient.setQueryData(materialKey, { asset: { id: "asset-1" }, parseVersions: [] });

    await invalidateProjectQueries(queryClient, "project-1", {
      ...projectEvent,
      resource: { id: "material-1", type: "source_material" },
    });

    expect(queryClient.getQueryState(materialKey)?.isInvalidated).toBe(true);
  });

  it("invalidates material detail caches when a generation job changes", async () => {
    const queryClient = new QueryClient();
    const materialKey = ["projects", "project-1", "materials", "material-1"] as const;
    const parseVersionsKey = [...materialKey, "parse-versions"] as const;
    queryClient.setQueryData(materialKey, { asset: { id: "asset-1" } });
    queryClient.setQueryData(parseVersionsKey, { items: [] });

    await invalidateProjectQueries(queryClient, "project-1", projectEvent);

    expect(queryClient.getQueryState(materialKey)?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(parseVersionsKey)?.isInvalidated).toBe(true);
  });

  it("refreshes the REST snapshot once when the stream ends on a permanent client error", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ error: { code: "FORBIDDEN" } }, { status: 403 }));
    const queryClient = new QueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    function ProjectEventProbe() {
      useProjectEvents("project-1");
      return null;
    }

    const view = render(
      createElement(QueryClientProvider, { client: queryClient }, createElement(ProjectEventProbe)),
    );

    await waitFor(() =>
      expect(invalidateQueries).toHaveBeenCalledWith({
        exact: true,
        queryKey: ["projects"],
        refetchType: "active",
      }),
    );
    expect(fetchMock).toHaveBeenCalledOnce();
    view.unmount();
    fetchMock.mockRestore();
  });

  it("removes the saved project sequence", () => {
    sessionStorage.setItem("shanhaiedu.events.project.project-1.sequence", "41");
    clearProjectLastSequence("project-1");
    expect(readProjectLastSequence("project-1")).toBeUndefined();
  });
});
