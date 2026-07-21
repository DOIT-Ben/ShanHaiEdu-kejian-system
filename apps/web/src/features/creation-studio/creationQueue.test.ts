import { describe, expect, it } from "vitest";
import {
  cancelCreationTask,
  completeCreationTask,
  enqueueCreationTask,
  retryCreationTask,
  type CreationQueueState,
} from "@/features/creation-studio/creationQueue";

describe("creation queue", () => {
  it("按导入顺序只运行一条任务，其余任务排队", () => {
    let queue: CreationQueueState = {};
    queue = enqueueCreationTask(queue, "shot-1");
    queue = enqueueCreationTask(queue, "shot-2");
    queue = enqueueCreationTask(queue, "shot-3");

    expect(queue["shot-1"]?.status).toBe("running");
    expect(queue["shot-2"]?.status).toBe("queued");
    expect(queue["shot-3"]?.status).toBe("queued");
  });

  it("完成或取消当前任务后自动推进下一条", () => {
    let queue: CreationQueueState = {};
    queue = enqueueCreationTask(queue, "shot-1");
    queue = enqueueCreationTask(queue, "shot-2");
    queue = enqueueCreationTask(queue, "shot-3");
    queue = completeCreationTask(queue, "shot-1");

    expect(queue["shot-1"]?.status).toBe("ready");
    expect(queue["shot-2"]?.status).toBe("running");
    queue = cancelCreationTask(queue, "shot-2");
    expect(queue["shot-2"]?.status).toBe("cancelled");
    expect(queue["shot-3"]?.status).toBe("running");
  });

  it("取消的任务可以重新加入队列", () => {
    let queue: CreationQueueState = enqueueCreationTask({}, "shot-1");
    queue = cancelCreationTask(queue, "shot-1");
    queue = retryCreationTask(queue, "shot-1");

    expect(queue["shot-1"]).toEqual({ attempts: 2, status: "running" });
  });
});
