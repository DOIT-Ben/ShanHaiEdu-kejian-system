export type CreationQueueStatus = "cancelled" | "failed" | "idle" | "queued" | "ready" | "running";

export type CreationQueueState = Record<
  string,
  {
    attempts: number;
    status: CreationQueueStatus;
  }
>;

function promoteNext(queue: CreationQueueState): CreationQueueState {
  if (Object.values(queue).some((task) => task.status === "running")) return queue;
  const nextId = Object.keys(queue).find((id) => queue[id]?.status === "queued");
  if (!nextId) return queue;
  const nextTask = queue[nextId];
  if (!nextTask) return queue;
  return { ...queue, [nextId]: { ...nextTask, status: "running" } };
}

export function enqueueCreationTask(queue: CreationQueueState, id: string): CreationQueueState {
  const running = Object.values(queue).some((task) => task.status === "running");
  return {
    ...queue,
    [id]: {
      attempts: (queue[id]?.attempts ?? 0) + 1,
      status: running ? ("queued" as const) : ("running" as const),
    },
  };
}

export function completeCreationTask(queue: CreationQueueState, id: string): CreationQueueState {
  const task = queue[id];
  if (!task) return queue;
  return promoteNext({ ...queue, [id]: { ...task, status: "ready" } });
}

export function cancelCreationTask(queue: CreationQueueState, id: string): CreationQueueState {
  const task = queue[id];
  if (!task) return queue;
  return promoteNext({ ...queue, [id]: { ...task, status: "cancelled" } });
}

export function retryCreationTask(queue: CreationQueueState, id: string): CreationQueueState {
  return enqueueCreationTask(
    { ...queue, [id]: { attempts: queue[id]?.attempts ?? 0, status: "idle" } },
    id,
  );
}
