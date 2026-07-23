import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { apiConfig } from "@/shared/api/config";
import {
  runSseSubscription,
  streamSseEvents,
  type SseEventEnvelope,
} from "@/shared/api/eventStream";

type JobStreamEvent = SseEventEnvelope;

type StreamJobEventsOptions = {
  fetchImpl?: typeof fetch;
  jobId: string;
  lastSequence?: number;
  onEvent: (event: JobStreamEvent) => void;
  signal?: AbortSignal;
};

function lastEventStorageKey(jobId: string) {
  return `shanhaiedu.events.job.${jobId}.sequence`;
}

export function readJobLastSequence(jobId: string) {
  try {
    const value = Number(sessionStorage.getItem(lastEventStorageKey(jobId)));
    return Number.isSafeInteger(value) && value > 0 ? value : undefined;
  } catch {
    return undefined;
  }
}

function saveJobLastSequence(jobId: string, sequence: number) {
  try {
    sessionStorage.setItem(lastEventStorageKey(jobId), String(sequence));
  } catch {
    // A live stream remains usable when session storage is unavailable.
  }
}

function clearJobLastSequence(jobId: string) {
  try {
    sessionStorage.removeItem(lastEventStorageKey(jobId));
  } catch {
    // A missing session storage must not prevent cursor recovery.
  }
}

export function streamJobEvents({
  fetchImpl = fetch,
  jobId,
  lastSequence,
  onEvent,
  signal,
}: StreamJobEventsOptions) {
  return streamSseEvents({
    fetchImpl,
    lastSequence,
    onEvent,
    signal,
    url: `${apiConfig.baseUrl}/generation-jobs/${encodeURIComponent(jobId)}/events/stream`,
  });
}

export function jobEventQueryKeys(jobId: string, projectId?: string) {
  return [
    ["generation-jobs", jobId],
    ...(projectId ? [["tasks", projectId] as const] : []),
  ] as const;
}

export function useJobEvents(jobId: string | undefined, projectId?: string) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!jobId) return;
    const abortController = new AbortController();
    const invalidate = async () => {
      const keys = jobEventQueryKeys(jobId, projectId);
      await Promise.all(
        keys.map((queryKey) =>
          queryClient.invalidateQueries({ queryKey, exact: true, refetchType: "active" }),
        ),
      );
    };
    void runSseSubscription({
      clearCursor: () => clearJobLastSequence(jobId),
      connect: (cursor, onEvent, signal) =>
        streamJobEvents({
          jobId,
          lastSequence: cursor,
          onEvent,
          signal,
        }),
      initialCursor: readJobLastSequence(jobId),
      onEvent: () => {
        void invalidate();
      },
      refreshSnapshot: () => invalidate(),
      signal: abortController.signal,
      writeCursor: (sequence) => saveJobLastSequence(jobId, sequence),
    }).catch(() => {
      if (!abortController.signal.aborted) void invalidate();
    });
    return () => abortController.abort();
  }, [jobId, projectId, queryClient]);
}
