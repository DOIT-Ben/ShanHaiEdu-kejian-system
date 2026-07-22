import {
  createMockTask,
  getMockRuntimeState,
  saveMockDraft,
  updateMockTask,
  updateMockNodeState,
  type MockRuntimeState,
} from "@/shared/api/mockClient";
import {
  cancelCreationTask,
  completeCreationTask,
  retryCreationTask,
  type CreationQueueState,
  type CreationQueueStatus,
} from "@/features/creation-studio/creationQueue";
import type { CreationStage } from "@/features/creation-studio/model";

export function readCreationDraft<T>(runtime: MockRuntimeState, key: string, fallback?: T) {
  const value = runtime.drafts[key]?.value;
  return value === undefined ? fallback : (value as T);
}

export function saveCreationDraft(
  key: string,
  value: unknown,
  options?: Parameters<typeof saveMockDraft>[2],
) {
  return saveMockDraft(key, value, options);
}

function toTaskStatus(status: CreationQueueStatus) {
  switch (status) {
    case "ready":
      return "review_required" as const;
    case "idle":
      return "draft" as const;
    default:
      return status;
  }
}

export function readCreationQueue(runtime: MockRuntimeState, key: string): CreationQueueState {
  const persisted = readCreationDraft<
    Record<string, { attempts: number; status?: CreationQueueStatus; taskId?: string }>
  >(runtime, key);
  if (!persisted) return {};
  return Object.fromEntries(
    Object.entries(persisted).map(([itemId, entry]) => {
      const task = entry.taskId
        ? runtime.tasks.find((candidate) => candidate.id === entry.taskId)
        : undefined;
      const status: CreationQueueStatus =
        task?.status === "review_required"
          ? "ready"
          : task?.status === "draft"
            ? "idle"
            : task?.status === "paused"
              ? "paused"
              : task?.status === "cancel_requested"
                ? "cancelled"
                : task?.status === "queued" ||
                    task?.status === "running" ||
                    task?.status === "cancelled" ||
                    task?.status === "failed"
                  ? task.status
                  : (entry.status ?? "idle");
      return [
        itemId,
        { attempts: entry.attempts, status, ...(entry.taskId ? { taskId: entry.taskId } : {}) },
      ];
    }),
  );
}

export function saveCreationQueue(
  key: string,
  queue: CreationQueueState,
  options?: Parameters<typeof saveMockDraft>[2],
) {
  const nextQueue: CreationQueueState = { ...queue };
  for (const [itemId, entry] of Object.entries(queue)) {
    const taskStatus = toTaskStatus(entry.status);
    const existing = entry.taskId
      ? getMockRuntimeState().tasks.find((task) => task.id === entry.taskId)
      : undefined;
    const task = existing
      ? updateMockTask(existing.id, {
          detail: "创作台生成任务",
          progress: taskStatus === "review_required" ? 100 : 0,
          retry_count: Math.max(0, entry.attempts - 1),
          stage: taskStatus === "review_required" ? "等待确认" : "创作台生成",
          status: taskStatus,
        })
      : createMockTask({
          detail: "创作台生成任务",
          progress: taskStatus === "review_required" ? 100 : 0,
          project_id: options?.projectId ?? null,
          retry_count: Math.max(0, entry.attempts - 1),
          stage: taskStatus === "review_required" ? "等待确认" : "创作台生成",
          status: taskStatus,
          title: "生成课堂素材",
        });
    if (task) nextQueue[itemId] = { ...entry, taskId: task.id };
  }
  saveCreationDraft(
    key,
    Object.fromEntries(
      Object.entries(nextQueue).map(([itemId, entry]) => [
        itemId,
        { attempts: entry.attempts, taskId: entry.taskId },
      ]),
    ),
    options,
  );
  return nextQueue;
}

export function resolveCreationStage(
  storedStage: CreationStage,
  taskStatus?: CreationQueueStatus,
): CreationStage {
  if (!taskStatus || taskStatus === "idle") return storedStage;
  if (taskStatus === "ready" && (storedStage === "adopted" || storedStage === "saved")) {
    return storedStage;
  }
  return taskStatus;
}

export function finishRunningCreationTask(
  key: string,
  itemId: string,
  options?: Parameters<typeof saveMockDraft>[2],
) {
  const queue = readCreationQueue(getMockRuntimeState(), key);
  if (queue[itemId]?.status !== "running") return undefined;
  return saveCreationQueue(key, completeCreationTask(queue, itemId), options);
}

type CreationTaskAction = "cancel" | "pause" | "resume" | "retry";

function findCreationTaskBinding(runtime: MockRuntimeState, taskId: string) {
  for (const [key, draft] of Object.entries(runtime.drafts)) {
    if (!key.startsWith("creation:") || !key.endsWith(":queue")) continue;
    if (!draft.value || typeof draft.value !== "object") continue;
    const itemId = Object.entries(
      draft.value as Record<string, { attempts?: number; taskId?: string }>,
    ).find(([, entry]) => entry.taskId === taskId)?.[0];
    if (itemId) return { draft, itemId, key };
  }
  return undefined;
}

export function applyCreationTaskAction(taskId: string, action: CreationTaskAction) {
  const runtime = getMockRuntimeState();
  const binding = findCreationTaskBinding(runtime, taskId);
  if (!binding) return false;
  if (action === "pause" || action === "resume") {
    updateMockTask(taskId, {
      stage: action === "pause" ? "已暂停" : "创作台生成",
      status: action === "pause" ? "paused" : "running",
    });
    return true;
  }
  const queue = readCreationQueue(runtime, binding.key);
  const nextQueue =
    action === "cancel"
      ? cancelCreationTask(queue, binding.itemId)
      : retryCreationTask(queue, binding.itemId);
  saveCreationQueue(binding.key, nextQueue, {
    lessonId: binding.draft.lesson_id ?? undefined,
    projectId: binding.draft.project_id ?? undefined,
  });
  return true;
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
