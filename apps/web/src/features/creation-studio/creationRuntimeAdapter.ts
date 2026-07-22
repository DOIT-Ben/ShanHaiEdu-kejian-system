import {
  getMockRuntimeState,
  saveMockDraft,
  updateMockNodeState,
  type MockRuntimeState,
} from "@/shared/api/mockClient";

export function readCreationDraft<T>(runtime: MockRuntimeState, key: string) {
  return runtime.drafts[key]?.value as T | undefined;
}

export function saveCreationDraft<T>(
  key: string,
  value: T,
  options?: Parameters<typeof saveMockDraft>[2],
) {
  return saveMockDraft(key, value, options);
}

export function readLatestCreationRuntime() {
  return getMockRuntimeState();
}

export function commitCreationNode(
  projectId: string,
  lessonId: string | null,
  nodeKey: string,
  patch: Parameters<typeof updateMockNodeState>[3],
) {
  return updateMockNodeState(projectId, lessonId, nodeKey, patch);
}
