import { parseWorkflowStatus } from "@/entities/workflow/model";
import type { MockRuntimeState } from "@/shared/api/mocks/runtimeTypes";

export class MockRuntimeStorageError extends Error {
  readonly code = "MOCK_RUNTIME_PERSISTENCE_FAILED";

  constructor() {
    super("无法保存本地演示数据，请检查浏览器存储空间或隐私设置。");
    this.name = "MockRuntimeStorageError";
  }
}

export function getMockBrowserStorage(): Storage | null {
  try {
    return typeof globalThis.localStorage === "undefined" ? null : globalThis.localStorage;
  } catch {
    return null;
  }
}

export function cloneMockRuntimeValue<T>(value: T): T {
  if (typeof globalThis.structuredClone === "function") return globalThis.structuredClone(value);
  return JSON.parse(JSON.stringify(value)) as T;
}

function isRuntimeState(value: unknown): value is MockRuntimeState {
  if (!value || typeof value !== "object") return false;
  const state = value as Record<string, unknown>;
  const isRecord = (item: unknown): item is Record<string, unknown> =>
    typeof item === "object" && item !== null && !Array.isArray(item);
  const recordsAreValid = (
    record: unknown,
    predicate: (item: Record<string, unknown>) => boolean,
  ) => isRecord(record) && Object.values(record).every((item) => isRecord(item) && predicate(item));
  const sessionIsValid =
    state.session === null ||
    (isRecord(state.session) &&
      typeof state.session.expires_at === "string" &&
      isRecord(state.session.user) &&
      (state.session.user.role === "teacher" || state.session.user.role === "admin"));
  return (
    state.schemaVersion === 1 &&
    Array.isArray(state.projects) &&
    state.projects.every(
      (project) =>
        isRecord(project) && typeof project.id === "string" && typeof project.title === "string",
    ) &&
    isRecord(state.textbookFiles) &&
    Object.values(state.textbookFiles).every(
      (files) =>
        Array.isArray(files) &&
        files.every(
          (file) =>
            isRecord(file) &&
            typeof file.id === "string" &&
            typeof file.project_id === "string" &&
            typeof file.name === "string",
        ),
    ) &&
    recordsAreValid(
      state.nodeStates,
      (node) =>
        typeof node.id === "string" &&
        typeof node.project_id === "string" &&
        typeof node.node_key === "string" &&
        typeof node.status === "string",
    ) &&
    Array.isArray(state.tasks) &&
    state.tasks.every(
      (task) => isRecord(task) && typeof task.id === "string" && typeof task.status === "string",
    ) &&
    Array.isArray(state.saveConflicts) &&
    state.saveConflicts.every(
      (conflict) => isRecord(conflict) && typeof conflict.id === "string",
    ) &&
    recordsAreValid(
      state.drafts,
      (draft) => typeof draft.key === "string" && typeof draft.revision === "number",
    ) &&
    sessionIsValid
  );
}

function normalizeRuntimeState(state: MockRuntimeState): MockRuntimeState {
  return {
    ...state,
    nodeStates: Object.fromEntries(
      Object.entries(state.nodeStates).map(([key, node]) => [
        key,
        { ...node, status: parseWorkflowStatus(node.status) },
      ]),
    ),
    tasks: state.tasks.map((task) => ({
      ...task,
      status: parseWorkflowStatus(task.status),
    })),
  };
}

export function readMockRuntimeState(storage: Storage | null, key: string, seed: MockRuntimeState) {
  if (!storage) return cloneMockRuntimeValue(seed);
  try {
    const raw = storage.getItem(key);
    if (!raw) return cloneMockRuntimeValue(seed);
    const parsed: unknown = JSON.parse(raw);
    return isRuntimeState(parsed) ? normalizeRuntimeState(parsed) : cloneMockRuntimeValue(seed);
  } catch {
    return cloneMockRuntimeValue(seed);
  }
}

export function persistMockRuntimeState(
  storage: Storage | null,
  key: string,
  state: MockRuntimeState,
) {
  if (!storage) throw new MockRuntimeStorageError();
  try {
    storage.setItem(key, JSON.stringify(state));
  } catch {
    throw new MockRuntimeStorageError();
  }
}
