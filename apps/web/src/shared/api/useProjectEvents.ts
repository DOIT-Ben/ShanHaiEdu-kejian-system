import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { apiConfig } from "@/shared/api/config";

const retryDelayMs = 1_500;
const errorRefreshDelayMs = 1_000;

type ProjectStreamEvent = {
  data: string;
  id: string;
  type: string;
};

type StreamProjectEventsOptions = {
  fetchImpl?: typeof fetch;
  lastEventId?: string;
  onEvent: (event: ProjectStreamEvent) => void;
  projectId: string;
  signal?: AbortSignal;
};

function lastEventStorageKey(projectId: string) {
  return `shanhaiedu.events.${projectId}.last-id`;
}

export function readProjectLastEventId(projectId: string) {
  try {
    return sessionStorage.getItem(lastEventStorageKey(projectId))?.trim() || undefined;
  } catch {
    return undefined;
  }
}

function saveProjectLastEventId(projectId: string, eventId: string) {
  try {
    sessionStorage.setItem(lastEventStorageKey(projectId), eventId);
  } catch {
    // A live stream remains usable when session storage is unavailable.
  }
}

function parseEventBlock(block: string): ProjectStreamEvent | null {
  let id = "";
  let type = "message";
  const data: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    const value = separator === -1 ? "" : line.slice(separator + 1).replace(/^ /, "");
    if (field === "id") id = value;
    else if (field === "event") type = value || "message";
    else if (field === "data") data.push(value);
  }
  return id || data.length > 0 ? { data: data.join("\n"), id, type } : null;
}

export async function streamProjectEvents({
  fetchImpl = fetch,
  lastEventId,
  onEvent,
  projectId,
  signal,
}: StreamProjectEventsOptions) {
  const headers = new Headers({ Accept: "text/event-stream" });
  if (lastEventId) headers.set("Last-Event-ID", lastEventId);
  const response = await fetchImpl(
    `${apiConfig.baseUrl}/projects/${encodeURIComponent(projectId)}/events/stream`,
    { credentials: "include", headers, signal },
  );
  if (!response.ok || !response.body) {
    throw new Error(`PROJECT_EVENT_STREAM_${String(response.status)}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let streamEnded = false;
  while (!streamEnded) {
    const { done, value } = await reader.read();
    streamEnded = done;
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const event = parseEventBlock(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      if (event) onEvent(event);
      boundary = buffer.indexOf("\n\n");
    }
  }
  const finalEvent = parseEventBlock(buffer);
  if (finalEvent) onEvent(finalEvent);
}

export function createRefreshThrottle(refresh: () => void, delayMs: number) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return {
    cancel() {
      if (timer) clearTimeout(timer);
      timer = undefined;
    },
    request() {
      if (timer) return;
      timer = setTimeout(() => {
        timer = undefined;
        refresh();
      }, delayMs);
    },
  };
}

export function useProjectEvents(projectId: string | undefined) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!projectId || apiConfig.mode !== "real") return;
    let stopped = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let lastEventId = readProjectLastEventId(projectId);
    const abortController = new AbortController();
    const refreshSnapshot = () => {
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["projects", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["tasks", projectId] }),
      ]);
    };
    const errorRefresh = createRefreshThrottle(refreshSnapshot, errorRefreshDelayMs);
    const connect = () => {
      void streamProjectEvents({
        lastEventId,
        onEvent: (event) => {
          if (event.id) {
            lastEventId = event.id;
            saveProjectLastEventId(projectId, event.id);
          }
          refreshSnapshot();
        },
        projectId,
        signal: abortController.signal,
      })
        .catch((reason: unknown) => {
          if (reason instanceof DOMException && reason.name === "AbortError") return;
          errorRefresh.request();
        })
        .finally(() => {
          if (!stopped) retryTimer = setTimeout(connect, retryDelayMs);
        });
    };
    connect();
    return () => {
      stopped = true;
      abortController.abort();
      if (retryTimer) clearTimeout(retryTimer);
      errorRefresh.cancel();
    };
  }, [projectId, queryClient]);
}
