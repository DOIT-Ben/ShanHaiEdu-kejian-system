import { beforeEach, describe, expect, it } from "vitest";
import { retryCreationTask } from "@/features/creation-studio/creationQueue";
import {
  readCreationQueue,
  saveCreationQueue,
} from "@/features/creation-studio/creationRuntimeAdapter";
import {
  createMockRuntimeStore,
  getMockRuntimeState,
  resetMockRuntime,
  updateMockTask,
} from "@/shared/api/mocks/runtime";

const queueKey = "creation:image:project:project-a:lesson:lesson-a:package:video-assets:queue";

describe("creation runtime adapter", () => {
  beforeEach(() => resetMockRuntime());

  it("uses the task center task as the queue status source", () => {
    const queue = saveCreationQueue(
      queueKey,
      { assetA: { attempts: 1, status: "running" } },
      { lessonId: "lesson-a", projectId: "project-a" },
    );
    const taskId = queue.assetA?.taskId;
    expect(taskId).toBeTruthy();
    expect(getMockRuntimeState().tasks.find((task) => task.id === taskId)?.status).toBe("running");

    updateMockTask(taskId ?? "", { status: "cancelled" });
    expect(readCreationQueue(getMockRuntimeState(), queueKey).assetA?.status).toBe("cancelled");

    saveCreationQueue(
      queueKey,
      retryCreationTask(readCreationQueue(getMockRuntimeState(), queueKey), "assetA"),
      { lessonId: "lesson-a", projectId: "project-a" },
    );
    const retriedTask = getMockRuntimeState().tasks.find((task) => task.id === taskId);
    expect(retriedTask?.status).toBe("running");
    expect(retriedTask?.retry_count).toBe(1);
  });

  it("restores queue bindings from persisted runtime state", () => {
    saveCreationQueue(
      queueKey,
      { assetA: { attempts: 1, status: "queued" } },
      { lessonId: "lesson-a", projectId: "project-a" },
    );
    const restored = createMockRuntimeStore({ storage: localStorage }).getState();
    expect(readCreationQueue(restored, queueKey).assetA?.status).toBe("queued");
    expect(restored.tasks.some((task) => task.title === "生成课堂素材")).toBe(true);
  });

  it("keeps legacy queue status until it is migrated to a task binding", () => {
    const runtime = getMockRuntimeState();
    runtime.drafts[queueKey] = {
      key: queueKey,
      lesson_id: "lesson-a",
      node_key: null,
      project_id: "project-a",
      revision: 1,
      updated_at: new Date().toISOString(),
      value: { assetA: { attempts: 1, status: "running" } },
    };
    expect(readCreationQueue(runtime, queueKey).assetA?.status).toBe("running");
  });
});
