import type { MockRuntimeState } from "@/shared/api/mocks/runtime";

export function getApprovedDraftValue<T>(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  nodeKey: string,
  fallback?: T,
): T | undefined {
  const draftKey = `project:${projectId}:lesson:${lessonId}:${nodeKey}`;
  const nodeStatus = runtime.nodeStates[`${projectId}:${lessonId}:${nodeKey}`]?.status;
  if (nodeStatus !== "approved") return fallback;
  const snapshot = runtime.drafts[`${draftKey}:approved`];
  if (snapshot) return snapshot.value as T;
  return fallback;
}
