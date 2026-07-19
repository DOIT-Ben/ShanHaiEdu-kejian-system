import { useSyncExternalStore } from "react";
import { createDefaultMockRuntimeState } from "@/shared/api/mocks/runtimeSeed";
import {
  cloneMockRuntimeValue,
  getMockBrowserStorage,
  persistMockRuntimeState,
  readMockRuntimeState,
} from "@/shared/api/mocks/runtimeStorage";
import type {
  CreateMockProjectInput,
  MockDraft,
  MockDraftOptions,
  MockNodeState,
  MockProject,
  MockRuntimeState,
  MockRuntimeStore,
  MockRuntimeStoreOptions,
  MockSaveConflict,
  MockTask,
  MockTextbookFile,
  MockTextbookFileInput,
  MockRuntimeListener,
  MockRuntimeStateUpdater,
} from "@/shared/api/mocks/runtimeTypes";

export type {
  CreateMockProjectInput,
  MockDraft,
  MockDraftOptions,
  MockNodeState,
  MockProject,
  MockRole,
  MockRuntimeState,
  MockRuntimeStore,
  MockRuntimeStoreOptions,
  MockSaveConflict,
  MockSession,
  MockTask,
  MockTextbookFile,
  MockTextbookFileInput,
} from "@/shared/api/mocks/runtimeTypes";
export { createDefaultMockRuntimeState } from "@/shared/api/mocks/runtimeSeed";
export {
  cloneMockRuntimeValue,
  persistMockRuntimeState,
  readMockRuntimeState,
} from "@/shared/api/mocks/runtimeStorage";

export const MOCK_RUNTIME_STORAGE_KEY = "shanhaiedu.mock-runtime.v1";

type StateUpdater = MockRuntimeStateUpdater;
type Listener = MockRuntimeListener;

let fallbackId = 0;

function createId() {
  try {
    return globalThis.crypto.randomUUID();
  } catch {
    fallbackId += 1;
    return `00000000-0000-4000-8000-${String(Date.now() + fallbackId)
      .padStart(12, "0")
      .slice(-12)}`;
  }
}

export function createMockEntityId() {
  return createId();
}

function nodeStateKey(projectId: string, lessonId: string | null, nodeKey: string) {
  return `${projectId}:${lessonId ?? "*"}:${nodeKey}`;
}

export function createMockRuntimeStore(options: MockRuntimeStoreOptions = {}): MockRuntimeStore {
  const storage = options.storage === undefined ? getMockBrowserStorage() : options.storage;
  const storageKey = options.storageKey ?? MOCK_RUNTIME_STORAGE_KEY;
  const seed = options.seed ?? createDefaultMockRuntimeState();
  const now = options.now ?? (() => new Date().toISOString());
  const idFactory = options.idFactory ?? createId;
  const listeners = new Set<Listener>();
  const taskTimers = new Map<string, ReturnType<typeof setTimeout>>();
  let state = readMockRuntimeState(storage, storageKey, seed);

  const setState = (updater: StateUpdater) => {
    const nextState = updater(state);
    persistMockRuntimeState(storage, storageKey, nextState);
    state = nextState;
    listeners.forEach((listener) => listener());
    return state;
  };
  const createTextbookFile = (projectId: string, input: MockTextbookFileInput) => {
    const file: MockTextbookFile = {
      id: idFactory(),
      project_id: projectId,
      name: input.name,
      size: input.size,
      type: input.type || "application/octet-stream",
      last_modified: input.lastModified ?? null,
      status: "uploaded",
      created_at: now(),
    };
    return file;
  };
  const addTextbookFile = (projectId: string, input: MockTextbookFileInput) => {
    const file = createTextbookFile(projectId, input);
    setState((current) => ({
      ...current,
      textbookFiles: {
        ...current.textbookFiles,
        [projectId]: [...(current.textbookFiles[projectId] ?? []), file],
      },
    }));
    return file;
  };
  const updateTextbookFile: MockRuntimeStore["updateTextbookFile"] = (projectId, fileId, patch) => {
    let updated: MockTextbookFile | undefined;
    setState((current) => ({
      ...current,
      textbookFiles: {
        ...current.textbookFiles,
        [projectId]: (current.textbookFiles[projectId] ?? []).map((file) => {
          if (file.id !== fileId) return file;
          updated = { ...file, ...patch };
          return updated;
        }),
      },
    }));
    return updated;
  };
  const createProject = (input: CreateMockProjectInput) => {
    const createdAt = now();
    const project: MockProject = {
      id: idFactory(),
      title: input.title.trim(),
      subject: "primary_math",
      grade: input.grade ?? null,
      textbook_edition: input.textbook_edition ?? null,
      knowledge_point: input.knowledge_point.trim(),
      status: "draft",
      automation_mode: input.automation_mode ?? "assisted",
      created_at: createdAt,
      updated_at: createdAt,
    };
    const textbookFile = input.textbook_file
      ? createTextbookFile(project.id, input.textbook_file)
      : null;
    setState((current) => ({
      ...current,
      projects: [project, ...current.projects],
      textbookFiles: textbookFile
        ? {
            ...current.textbookFiles,
            [project.id]: [...(current.textbookFiles[project.id] ?? []), textbookFile],
          }
        : current.textbookFiles,
    }));
    return project;
  };
  const updateProject: MockRuntimeStore["updateProject"] = (projectId, patch) => {
    let updated: MockProject | undefined;
    setState((current) => ({
      ...current,
      projects: current.projects.map((project) => {
        if (project.id !== projectId) return project;
        updated = { ...project, ...patch, updated_at: now() };
        return updated;
      }),
    }));
    return updated;
  };
  const saveDraft: MockRuntimeStore["saveDraft"] = (key, value, draftOptions = {}) => {
    const previous = state.drafts[key];
    const draft: MockDraft<typeof value> = {
      key,
      value: cloneMockRuntimeValue(value),
      project_id: draftOptions.projectId ?? previous?.project_id ?? null,
      lesson_id: draftOptions.lessonId ?? previous?.lesson_id ?? null,
      node_key: draftOptions.nodeKey ?? previous?.node_key ?? null,
      revision: (previous?.revision ?? 0) + 1,
      updated_at: now(),
    };
    setState((current) => ({ ...current, drafts: { ...current.drafts, [key]: draft } }));
    return draft;
  };
  const updateNodeState: MockRuntimeStore["updateNodeState"] = (
    projectId,
    lessonId,
    nodeKey,
    patch,
  ) => {
    const key = nodeStateKey(projectId, lessonId, nodeKey);
    const existing = state.nodeStates[key];
    const node: MockNodeState = {
      id: existing?.id ?? idFactory(),
      project_id: projectId,
      lesson_id: lessonId,
      node_key: nodeKey,
      title: patch.title ?? existing?.title ?? nodeKey,
      status: patch.status ?? existing?.status ?? "draft",
      revision: patch.revision ?? (existing?.revision ?? 0) + 1,
      updated_at: patch.updated_at ?? now(),
      stale_reason: Object.prototype.hasOwnProperty.call(patch, "stale_reason")
        ? (patch.stale_reason ?? null)
        : (existing?.stale_reason ?? null),
    };
    setState((current) => ({
      ...current,
      nodeStates: { ...current.nodeStates, [key]: node },
    }));
    return node;
  };
  let scheduleFinalVideoTask: (task: MockTask) => void = () => undefined;
  const updateTask: MockRuntimeStore["updateTask"] = (taskId, patch) => {
    let updated: MockTask | undefined;
    setState((current) => ({
      ...current,
      tasks: current.tasks.map((task) => {
        if (task.id !== taskId) return task;
        updated = { ...task, ...patch, updated_at: now() };
        return updated;
      }),
    }));
    if (updated?.status === "cancel_requested") {
      const timer = taskTimers.get(updated.id);
      if (timer) clearTimeout(timer);
      taskTimers.delete(updated.id);
      scheduleFinalVideoTask(updated);
    } else if (updated?.status === "running") {
      scheduleFinalVideoTask(updated);
    } else if (updated) {
      const timer = taskTimers.get(updated.id);
      if (timer) clearTimeout(timer);
      taskTimers.delete(updated.id);
    }
    return updated;
  };
  scheduleFinalVideoTask = (task: MockTask) => {
    const linkedFinalVideoNode = Object.values(state.nodeStates).find(
      (node) =>
        node.id === task.node_run_id &&
        node.node_key === "final-video" &&
        node.project_id === task.project_id,
    );
    const legacyTaskReference = task.node_run_id?.match(/^(.+):([^:]+):final-video$/);
    const linkedLegacyFinalVideoNode = legacyTaskReference
      ? Object.values(state.nodeStates).find(
          (node) =>
            node.node_key === "final-video" &&
            node.project_id === task.project_id &&
            node.project_id === legacyTaskReference[1] &&
            node.lesson_id === legacyTaskReference[2],
        )
      : undefined;
    if (
      (task.status !== "running" && task.status !== "cancel_requested") ||
      (!linkedFinalVideoNode && !linkedLegacyFinalVideoNode) ||
      taskTimers.has(task.id)
    ) {
      return;
    }
    const timer = setTimeout(
      () => {
        taskTimers.delete(task.id);
        const currentTask = state.tasks.find((item) => item.id === task.id);
        if (task.status === "cancel_requested") {
          if (currentTask?.status !== "cancel_requested") return;
          updateTask(task.id, { stage: "已取消", status: "cancelled" });
          return;
        }
        if (currentTask?.status !== "running") return;
        updateTask(task.id, {
          progress: 100,
          stage: "等待接收视频文件",
          status: "review_required",
        });
      },
      task.status === "cancel_requested" ? 180 : 650,
    );
    taskTimers.set(task.id, timer);
  };
  const createTask: MockRuntimeStore["createTask"] = (input) => {
    const task: MockTask = {
      id: idFactory(),
      project_id: input.project_id ?? null,
      node_run_id: input.node_run_id ?? null,
      title: input.title,
      detail: input.detail,
      stage: input.stage,
      status: input.status,
      progress: input.progress ?? 0,
      retry_count: input.retry_count ?? 0,
      updated_at: now(),
    };
    setState((current) => ({ ...current, tasks: [task, ...current.tasks] }));
    scheduleFinalVideoTask(task);
    return task;
  };
  state.tasks.forEach(scheduleFinalVideoTask);
  const createSaveConflict: MockRuntimeStore["createSaveConflict"] = (input) => {
    const conflict: MockSaveConflict = {
      ...input,
      id: idFactory(),
      status: "open",
      created_at: now(),
      resolved_at: null,
    };
    setState((current) => ({ ...current, saveConflicts: [conflict, ...current.saveConflicts] }));
    return conflict;
  };

  return {
    getState: () => state,
    setState,
    reset: () => {
      taskTimers.forEach((timer) => clearTimeout(timer));
      taskTimers.clear();
      const restored = cloneMockRuntimeValue(seed);
      const nextState = setState(() => restored);
      nextState.tasks.forEach(scheduleFinalVideoTask);
      return nextState;
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    createProject,
    getProject: (projectId) => state.projects.find((project) => project.id === projectId),
    updateProject,
    addTextbookFile,
    updateTextbookFile,
    getNodeState: (projectId, lessonId, nodeKey) =>
      state.nodeStates[nodeStateKey(projectId, lessonId, nodeKey)],
    updateNodeState,
    listTasks: (projectId) =>
      projectId ? state.tasks.filter((task) => task.project_id === projectId) : state.tasks,
    createTask,
    updateTask,
    createSaveConflict,
    resolveSaveConflict: (conflictId, status) => {
      let resolved: MockSaveConflict | undefined;
      setState((current) => ({
        ...current,
        saveConflicts: current.saveConflicts.map((conflict) => {
          if (conflict.id !== conflictId) return conflict;
          resolved = { ...conflict, status, resolved_at: now() };
          return resolved;
        }),
      }));
      return resolved;
    },
    saveDraft,
    setSession: (session) => {
      setState((current) => ({ ...current, session }));
    },
  };
}

export const mockRuntime = createMockRuntimeStore();

export function getMockRuntimeState() {
  return mockRuntime.getState();
}

export function subscribe(listener: Listener) {
  return mockRuntime.subscribe(listener);
}

export function resetMockRuntime() {
  return mockRuntime.reset();
}

export function createMockProject(input: CreateMockProjectInput, store = mockRuntime) {
  return store.createProject(input);
}

export function getMockProject(projectId: string, store = mockRuntime) {
  return store.getProject(projectId);
}

export function updateMockProject(
  projectId: string,
  patch: Parameters<MockRuntimeStore["updateProject"]>[1],
  store = mockRuntime,
) {
  return store.updateProject(projectId, patch);
}

export function saveMockDraft<T>(
  key: string,
  value: T,
  options?: MockDraftOptions,
  store = mockRuntime,
) {
  return store.saveDraft(key, value, options);
}

export function getMockDraft<T = unknown>(key: string, store = mockRuntime) {
  return store.getState().drafts[key] as MockDraft<T> | undefined;
}

export function listMockTextbookFiles(projectId: string, store = mockRuntime) {
  return store.getState().textbookFiles[projectId] ?? [];
}

export function addMockTextbookFile(
  projectId: string,
  input: MockTextbookFileInput,
  store = mockRuntime,
) {
  return store.addTextbookFile(projectId, input);
}

export function updateMockTextbookFile(
  projectId: string,
  fileId: string,
  patch: Parameters<MockRuntimeStore["updateTextbookFile"]>[2],
  store = mockRuntime,
) {
  return store.updateTextbookFile(projectId, fileId, patch);
}

export function getMockNodeState(
  projectId: string,
  lessonId: string | null,
  nodeKey: string,
  store = mockRuntime,
) {
  return store.getNodeState(projectId, lessonId, nodeKey);
}

export function updateMockNodeState(
  projectId: string,
  lessonId: string | null,
  nodeKey: string,
  patch: Parameters<MockRuntimeStore["updateNodeState"]>[3],
  store = mockRuntime,
) {
  return store.updateNodeState(projectId, lessonId, nodeKey, patch);
}

export function listMockTasks(projectId?: string, store = mockRuntime) {
  return store.listTasks(projectId);
}

export function createMockTask(
  input: Parameters<MockRuntimeStore["createTask"]>[0],
  store = mockRuntime,
) {
  return store.createTask(input);
}

export function updateMockTask(
  taskId: string,
  patch: Parameters<MockRuntimeStore["updateTask"]>[1],
  store = mockRuntime,
) {
  return store.updateTask(taskId, patch);
}

export function createMockSaveConflict(
  input: Parameters<MockRuntimeStore["createSaveConflict"]>[0],
  store = mockRuntime,
) {
  return store.createSaveConflict(input);
}

export function listMockSaveConflicts(projectId?: string, store = mockRuntime) {
  const conflicts = store.getState().saveConflicts;
  return projectId ? conflicts.filter((conflict) => conflict.project_id === projectId) : conflicts;
}

export function resolveMockSaveConflict(
  conflictId: string,
  status: Extract<MockSaveConflict["status"], "replaced" | "kept">,
  store = mockRuntime,
) {
  return store.resolveSaveConflict(conflictId, status);
}

export function useMockRuntime<T = MockRuntimeState>(selector?: (state: MockRuntimeState) => T) {
  return useSyncExternalStore(
    mockRuntime.subscribe,
    () => (selector ? selector(mockRuntime.getState()) : (mockRuntime.getState() as T)),
    () => (selector ? selector(mockRuntime.getState()) : (mockRuntime.getState() as T)),
  );
}
