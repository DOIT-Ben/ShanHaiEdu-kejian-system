import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { apiConfig } from "@/shared/api/config";
import {
  runSseSubscription,
  streamSseEvents,
  type SseEventEnvelope,
} from "@/shared/api/eventStream";

type ProjectStreamEvent = SseEventEnvelope;

type StreamProjectEventsOptions = {
  fetchImpl?: typeof fetch;
  lastSequence?: number;
  onEvent: (event: ProjectStreamEvent) => void;
  projectId: string;
  signal?: AbortSignal;
};

function lastEventStorageKey(projectId: string) {
  return `shanhaiedu.events.project.${projectId}.sequence`;
}

export function readProjectLastSequence(projectId: string) {
  try {
    const value = Number(sessionStorage.getItem(lastEventStorageKey(projectId)));
    return Number.isSafeInteger(value) && value > 0 ? value : undefined;
  } catch {
    return undefined;
  }
}

function saveProjectLastSequence(projectId: string, sequence: number) {
  try {
    sessionStorage.setItem(lastEventStorageKey(projectId), String(sequence));
  } catch {
    // A live stream remains usable when session storage is unavailable.
  }
}

export function clearProjectLastSequence(projectId: string) {
  try {
    sessionStorage.removeItem(lastEventStorageKey(projectId));
  } catch {
    // A missing session storage must not prevent cursor recovery.
  }
}

export function streamProjectEvents({
  fetchImpl = fetch,
  lastSequence,
  onEvent,
  projectId,
  signal,
}: StreamProjectEventsOptions) {
  return streamSseEvents({
    fetchImpl,
    lastSequence,
    onEvent,
    signal,
    url: `${apiConfig.baseUrl}/projects/${encodeURIComponent(projectId)}/events/stream`,
  });
}

export function projectEventQueryKeys(projectId: string, event: ProjectStreamEvent) {
  if (event.resource.type === "generation_job") {
    return [
      ["generation-jobs", event.resource.id],
      ["tasks", projectId],
    ] as const;
  }
  if (event.resource.type === "project") {
    return [["projects", projectId], ["projects"]] as const;
  }
  return [["projects", projectId, "workflow"]] as const;
}

async function invalidateProjectQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string,
  event?: ProjectStreamEvent,
) {
  const keys = event
    ? projectEventQueryKeys(projectId, event)
    : [
        ["projects"],
        ["projects", projectId],
        ["projects", projectId, "workflow"],
        ["tasks", projectId],
      ];
  await Promise.all(
    keys.map((queryKey) =>
      queryClient.invalidateQueries({ queryKey, exact: true, refetchType: "active" }),
    ),
  );
}

export function useProjectEvents(projectId: string | undefined) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!projectId || apiConfig.mode !== "real") return;
    const abortController = new AbortController();
    const clearCursor = () => clearProjectLastSequence(projectId);
    void runSseSubscription({
      clearCursor,
      connect: (cursor, onEvent, signal) =>
        streamProjectEvents({
          lastSequence: cursor,
          onEvent,
          projectId,
          signal,
        }),
      initialCursor: readProjectLastSequence(projectId),
      onEvent: (event) => {
        void invalidateProjectQueries(queryClient, projectId, event);
      },
      refreshSnapshot: () => invalidateProjectQueries(queryClient, projectId),
      signal: abortController.signal,
      writeCursor: (sequence) => saveProjectLastSequence(projectId, sequence),
    });
    return () => abortController.abort();
  }, [projectId, queryClient]);
}
