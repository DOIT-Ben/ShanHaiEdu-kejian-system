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

const artifactResourceTypes = new Set([
  "artifact",
  "artifact_draft",
  "artifact_version",
  "approval",
]);
const assetResourceTypes = new Set([
  "project_asset_slot",
  "asset_binding",
  "save_to_project_operation",
]);

function materialEventQueryKeys(projectId: string, materialId: string) {
  return [
    ["projects", projectId, "materials"],
    ["projects", projectId, "materials", materialId, "file-asset"],
    ["projects", projectId, "materials", materialId, "parse-versions"],
    ["projects", projectId, "workflow"],
  ] as const;
}

function artifactEventQueryKeys(projectId: string, event: ProjectStreamEvent) {
  const projectKeys = [
    ["projects", projectId, "artifacts"],
    ["projects", projectId, "workflow"],
  ] as const;
  return event.resource.type === "artifact"
    ? ([["artifacts", event.resource.id], ...projectKeys] as const)
    : projectKeys;
}

function assetEventQueryKeys(projectId: string) {
  return [
    ["projects", projectId, "asset-slots"],
    ["projects", projectId, "asset-package"],
    ["projects", projectId, "workflow"],
  ] as const;
}

export function projectEventQueryKeys(projectId: string, event: ProjectStreamEvent) {
  const workflowKey = ["projects", projectId, "workflow"] as const;
  if (event.resource.type === "generation_job") {
    return [
      ["generation-jobs", event.resource.id],
      ["tasks", projectId],
    ] as const;
  }
  if (event.resource.type === "project") {
    return [["projects", projectId], ["projects"]] as const;
  }
  if (event.resource.type === "automation_policy") {
    return [["projects", projectId, "automation-policy"]] as const;
  }
  if (event.resource.type === "lesson_collection") {
    return [
      ["projects", projectId, "lessons"],
      ["projects", projectId],
      ["projects"],
      workflowKey,
    ] as const;
  }
  if (event.resource.type === "lesson") {
    return [
      ["projects", projectId, "lessons"],
      ["lessons", event.resource.id],
      workflowKey,
    ] as const;
  }
  if (event.resource.type === "source_material") {
    return materialEventQueryKeys(projectId, event.resource.id);
  }
  if (artifactResourceTypes.has(event.resource.type))
    return artifactEventQueryKeys(projectId, event);
  if (assetResourceTypes.has(event.resource.type)) return assetEventQueryKeys(projectId);
  // Unknown resources must not leave the project shell stale. Refresh the
  // cheap project summaries as well as the workflow snapshot; the next
  // server-side event can narrow the affected family again.
  return [["projects", projectId], ["projects"], workflowKey] as const;
}

async function invalidateProjectQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string,
  event?: ProjectStreamEvent,
) {
  if (!event) {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["projects"], exact: true, refetchType: "active" }),
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId],
        exact: false,
        refetchType: "active",
      }),
      queryClient.invalidateQueries({ queryKey: ["lessons"], exact: false, refetchType: "active" }),
      queryClient.invalidateQueries({
        queryKey: ["artifacts"],
        exact: false,
        refetchType: "active",
      }),
      queryClient.invalidateQueries({
        queryKey: ["tasks", projectId],
        exact: true,
        refetchType: "active",
      }),
    ]);
    return;
  }
  const keys = projectEventQueryKeys(projectId, event);
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
