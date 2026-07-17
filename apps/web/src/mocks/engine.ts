import { db, emitEvent, nextId, nowIso, type MockJob } from "./db";
import { placeholderSvg } from "./seed";

/**
 * Mock 任务推进引擎：queued → running →（completed | partially_completed | failed）。
 * 每次状态变化写入事件日志（SSE 订阅者按 sequence_no 增量收取）。
 * 不伪造百分比，只推进真实阶段；页面刷新后从 REST 恢复。
 */

const timers = new Set<ReturnType<typeof setTimeout>>();

export function clearAllTimers(): void {
  for (const timer of timers) clearTimeout(timer);
  timers.clear();
}

function schedule(fn: () => void, ms: number): void {
  const delay = Math.max(0, Math.round(ms * db.speedFactor));
  if (delay === 0) {
    fn();
    return;
  }
  const timer = setTimeout(() => {
    timers.delete(timer);
    fn();
  }, delay);
  timers.add(timer);
}

function jobEvent(job: MockJob, type: string, payload: Record<string, unknown> = {}): void {
  emitEvent({
    event_type: type,
    project_id: job.project_id,
    resource: { type: "generation_job", id: job.id },
    payload: { status: job.status, node_run_id: job.node_run_id, batch_id: job.batch_id, ...payload },
  });
}

function nodeEvent(nodeRunId: string, projectId: string | null, status: string): void {
  emitEvent({
    event_type: "node_run.status_changed",
    project_id: projectId,
    resource: { type: "node_run", id: nodeRunId },
    payload: { status },
  });
}

export interface StartJobInput {
  kind: string;
  title: string;
  projectId?: string | null;
  lessonId?: string | null;
  nodeRunId?: string | null;
  batchId?: string | null;
  totalItems?: number | null;
  /** 各阶段时长（毫秒，speedFactor 缩放）。 */
  phaseMs?: [number, number];
  onComplete: (job: MockJob) => void;
  /** 结束状态覆盖（partial/failed 场景）。 */
  finalStatus?: MockJob["status"];
  failedItemKeys?: string[];
  error?: { code: string; message: string; retryable: boolean } | null;
}

export function startJob(input: StartJobInput): MockJob {
  const job: MockJob = {
    id: nextId(),
    kind: input.kind,
    status: "queued",
    title: input.title,
    project_id: input.projectId ?? null,
    lesson_id: input.lessonId ?? null,
    node_run_id: input.nodeRunId ?? null,
    batch_id: input.batchId ?? null,
    phase_label: "排队中",
    completed_items: input.totalItems ? 0 : null,
    total_items: input.totalItems ?? null,
    failed_item_keys: [],
    error: null,
    created_at: nowIso(),
    updated_at: nowIso(),
    finished_at: null,
  };
  db.jobs.set(job.id, job);
  jobEvent(job, "generation_job.created");

  if (job.node_run_id) {
    const run = db.nodeRuns.get(job.node_run_id);
    if (run) {
      run.status = "queued";
      run.active_job_id = job.id;
      run.updated_at = nowIso();
      nodeEvent(run.id, run.project_id, run.status);
    }
  }

  const [toRunning, toDone] = input.phaseMs ?? [900, 2600];

  schedule(() => {
    if (job.status !== "queued") return; // 已取消
    job.status = "running";
    job.phase_label = "正在生成";
    job.updated_at = nowIso();
    jobEvent(job, "generation_job.status_changed");
    if (job.node_run_id) {
      const run = db.nodeRuns.get(job.node_run_id);
      if (run) {
        run.status = "running";
        run.updated_at = nowIso();
        nodeEvent(run.id, run.project_id, run.status);
      }
    }
    schedule(() => {
      if (job.status !== "running") return;
      const final = input.finalStatus ?? "completed";
      job.status = final;
      job.phase_label = null;
      job.failed_item_keys = input.failedItemKeys ?? [];
      job.error = input.error ?? null;
      if (job.total_items != null) {
        job.completed_items = job.total_items - job.failed_item_keys.length;
      }
      job.finished_at = nowIso();
      job.updated_at = nowIso();
      if (job.node_run_id) {
        const run = db.nodeRuns.get(job.node_run_id);
        if (run) run.active_job_id = null;
      }
      input.onComplete(job);
      jobEvent(job, "generation_job.finished");
    }, toDone);
  }, toRunning);

  return job;
}

export function cancelJob(jobId: string): boolean {
  const job = db.jobs.get(jobId);
  if (!job) return false;
  if (job.status !== "queued" && job.status !== "running" && job.status !== "waiting_provider") {
    return false;
  }
  job.status = "cancel_requested";
  job.updated_at = nowIso();
  jobEvent(job, "generation_job.status_changed");
  schedule(() => {
    job.status = "cancelled";
    job.finished_at = nowIso();
    job.updated_at = nowIso();
    if (job.node_run_id) {
      const run = db.nodeRuns.get(job.node_run_id);
      if (run) {
        run.status = "cancelled";
        run.active_job_id = null;
        run.updated_at = nowIso();
        nodeEvent(run.id, run.project_id, run.status);
      }
    }
    jobEvent(job, "generation_job.finished");
  }, 500);
  return true;
}

/** 生成图片/视频候选结果（写入 results 表）。 */
export function produceResults(input: {
  batchId?: string | null;
  nodeRunId?: string | null;
  itemKey: string;
  mediaType: "image" | "video" | "ppt_page" | "document" | "audio";
  count: number;
  labelPrefix: string;
  tone?: string;
  durationSeconds?: number | null;
}): string[] {
  const created: string[] = [];
  for (let i = 0; i < input.count; i += 1) {
    const id = nextId();
    db.results.set(id, {
      id,
      batch_id: input.batchId ?? null,
      node_run_id: input.nodeRunId ?? null,
      item_key: input.itemKey,
      media_type: input.mediaType,
      review_state: "pending",
      technical_check: "passed",
      technical_check_detail: null,
      preview_url: placeholderSvg(`${input.labelPrefix} 候选${String.fromCharCode(65 + i)}`, input.tone ?? "#315ef5"),
      duration_seconds: input.durationSeconds ?? null,
      width: input.mediaType === "video" ? 1280 : 1024,
      height: input.mediaType === "video" ? 720 : 1024,
      saved_binding_id: null,
      created_at: nowIso(),
    });
    created.push(id);
  }
  return created;
}
