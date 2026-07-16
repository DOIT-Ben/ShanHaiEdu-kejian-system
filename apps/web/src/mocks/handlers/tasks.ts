import { http } from "msw";
import { getDb } from "../db";
import { cancelTask, retryTask } from "../engine";
import { api, fail, guard, ok, paginate, simulateLatency } from "./http";

export const taskHandlers = [
  http.get(api("/tasks"), async ({ request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const url = new URL(request.url);
    const pageSize = Number.parseInt(url.searchParams.get("page_size") ?? "50", 10);
    const items = [...db.tasks.values()].sort((a, b) => b.created_at.localeCompare(a.created_at));
    const { page, nextCursor } = paginate(items, url.searchParams.get("cursor"), pageSize);
    return ok(page, { meta: { next_cursor: nextCursor } });
  }),

  http.get(api("/projects/:projectId/tasks"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const projectId = String(params.projectId);
    const url = new URL(request.url);
    const status = url.searchParams.get("status");
    const lessonId = url.searchParams.get("lesson_id");
    const nodeKey = url.searchParams.get("node_key");
    const pageSize = Number.parseInt(url.searchParams.get("page_size") ?? "50", 10);

    let items = [...db.tasks.values()].filter((t) => t.project_id === projectId);
    if (status) items = items.filter((t) => t.status === status);
    if (lessonId) items = items.filter((t) => t.lesson_id === lessonId);
    if (nodeKey) items = items.filter((t) => t.node_key === nodeKey);
    items.sort((a, b) => b.created_at.localeCompare(a.created_at));
    const { page, nextCursor } = paginate(items, url.searchParams.get("cursor"), pageSize);
    return ok(page, { meta: { next_cursor: nextCursor } });
  }),

  http.get(api("/tasks/:taskId"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    const task = getDb().tasks.get(String(params.taskId));
    if (!task) return fail(404, "NOT_FOUND", "任务不存在。");
    return ok(task);
  }),

  http.post(api("/tasks/:taskId/cancel"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const task = getDb().tasks.get(String(params.taskId));
    if (!task) return fail(404, "NOT_FOUND", "任务不存在。");
    if (task.status === "completed" || task.status === "failed" || task.status === "cancelled") {
      return fail(409, "NOT_CANCELLABLE", "任务已结束，无法取消。");
    }
    const cancelled = cancelTask(task.task_id);
    return ok(cancelled, { status: 202 });
  }),

  http.post(api("/tasks/:taskId/retry"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const idempotencyKey = request.headers.get("idempotency-key");
    if (!idempotencyKey || idempotencyKey.length < 16) {
      return fail(400, "IDEMPOTENCY_KEY_REQUIRED", "缺少幂等键，请刷新后重试。");
    }
    const original = db.tasks.get(String(params.taskId));
    if (!original) return fail(404, "NOT_FOUND", "任务不存在。");
    if (original.status !== "failed") {
      return fail(409, "NOT_RETRYABLE", "只有失败的任务可以重试。");
    }
    if (!original.retryable) {
      return fail(409, "NOT_RETRYABLE", "该任务不支持自动重试，请调整内容后重新提交。");
    }
    const idemKey = `retry:${original.task_id}:${idempotencyKey}`;
    if (db.idempotency.has(idemKey)) {
      const existing = db.tasks.get(db.idempotency.get(idemKey)!);
      if (existing) return ok(existing, { status: 202 });
    }
    const next = retryTask(original.task_id);
    if (!next) return fail(409, "NOT_RETRYABLE", "任务无法重试。");
    db.idempotency.set(idemKey, next.task_id);
    return ok(next, { status: 202 });
  }),
];
