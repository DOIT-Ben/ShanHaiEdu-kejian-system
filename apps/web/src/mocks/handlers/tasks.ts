import { http, HttpResponse } from "msw";
import { db, emitEvent, nextId, nowIso } from "../db";
import { API, fail, idempotent, notFound, ok, requireSession, simulateLatency } from "../http";
import { cancelJob, startJob, produceResults } from "../engine";
import { isTaskActive } from "@/shared/lib/status";
import { completeNodeGeneration } from "./runs";

function jobPayload(job: NonNullable<ReturnType<typeof db.jobs.get>>) {
  const { plan: _plan, ...rest } = job;
  return rest;
}

/** 任务中心 + SSE 事件流 + 素材 + 交付 + 预算。 */
export const taskHandlers = [
  http.get(API("/generation-jobs"), async ({ request }) => {
    await simulateLatency(110);
    const denied = requireSession();
    if (denied) return denied;
    const url = new URL(request.url);
    const projectId = url.searchParams.get("project_id");
    const active = url.searchParams.get("active");
    const items = [...db.jobs.values()]
      .filter((job) => !projectId || job.project_id === projectId)
      .filter((job) => active !== "true" || isTaskActive(job.status))
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .map(jobPayload);
    return ok({ items }, { meta: { next_cursor: null } });
  }),

  http.get(API("/generation-jobs/:jobId"), async ({ params }) => {
    await simulateLatency(80);
    const denied = requireSession();
    if (denied) return denied;
    const job = db.jobs.get(params.jobId as string);
    if (!job) return notFound("任务");
    return ok(jobPayload(job));
  }),

  http.post(API("/generation-jobs/:jobId/cancel"), async ({ params, request }) => {
    await simulateLatency(120);
    const denied = requireSession();
    if (denied) return denied;
    const job = db.jobs.get(params.jobId as string);
    if (!job) return notFound("任务");
    return idempotent(request, `cancel:${job.id}`, () => {
      const accepted = cancelJob(job.id);
      if (!accepted) {
        return fail(409, "JOB_NOT_CANCELLABLE", "任务已结束，无法取消。");
      }
      return {
        data: { job_id: job.id, status: "running" as const, events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
        status: 202,
      };
    });
  }),

  http.post(API("/generation-jobs/:jobId/retry"), async ({ params, request }) => {
    await simulateLatency(150);
    const denied = requireSession();
    if (denied) return denied;
    const job = db.jobs.get(params.jobId as string);
    if (!job) return notFound("任务");
    if (job.status !== "failed" && job.status !== "partially_completed") {
      return fail(409, "JOB_NOT_RETRYABLE", "只有失败或部分完成的任务可以重试。");
    }
    const body = (await request.json().catch(() => ({}))) as { item_keys?: string[] } | null;
    const retryKeys = body?.item_keys?.length ? body.item_keys : job.failed_item_keys;
    return idempotent(request, `retry:${job.id}:${retryKeys.join(",")}`, () => {
      const retryJob = startJob({
        kind: job.kind,
        title: `${job.title}（重试）`,
        projectId: job.project_id,
        lessonId: job.lesson_id,
        nodeRunId: job.node_run_id,
        batchId: job.batch_id,
        totalItems: retryKeys.length || null,
        phaseMs: [600, 2000],
        onComplete: () => {
          // 重试成功：清除失败项
          if (job.node_run_id) {
            completeNodeGeneration(job.node_run_id);
          }
          if (job.batch_id) {
            const batch = db.batches.get(job.batch_id);
            if (batch) {
              for (const key of retryKeys) {
                const item = batch.items.find((i) => i.item_key === key);
                if (item) {
                  item.status = "review_required";
                  produceResults({
                    batchId: batch.id,
                    itemKey: item.item_key,
                    mediaType: batch.studio_type === "video" ? "video" : "image",
                    count: 2,
                    labelPrefix: `${item.title}（重试）`,
                  });
                }
              }
              batch.updated_at = nowIso();
              batch.etag += 1;
            }
          }
        },
      });
      return {
        data: { job_id: retryJob.id, status: "queued" as const, events_url: `/api/v2/generation-jobs/${retryJob.id}/events/stream` },
        status: 202,
      };
    });
  }),

  // ── SSE 流（全局 / 项目 / 任务） ─────────────────────
  http.get(API("/events/stream"), ({ request }) => sseResponse(request, () => true)),
  http.get(API("/projects/:projectId/events/stream"), ({ request, params }) =>
    sseResponse(request, (event) => event.project_id === params.projectId),
  ),
  http.get(API("/generation-jobs/:jobId/events/stream"), ({ request, params }) =>
    sseResponse(request, (event) => event.resource.id === params.jobId),
  ),

  // ── 素材成果 ─────────────────────────────────────────
  http.get(API("/projects/:projectId/assets"), async ({ params, request }) => {
    await simulateLatency(130);
    const denied = requireSession();
    if (denied) return denied;
    const projectId = params.projectId as string;
    if (!db.projects.get(projectId)) return notFound("项目");
    const url = new URL(request.url);
    const kind = url.searchParams.get("kind");
    const lessonId = url.searchParams.get("lesson_id");
    const items = [...db.assets.values()]
      .filter((a) => a.project_id === projectId)
      .filter((a) => !kind || a.kind === kind)
      .filter((a) => !lessonId || a.lesson_id === lessonId)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));

    // 顶部三张成果卡（教案 / PPT / 课堂导入视频）
    const lessons = [...db.lessons.values()].filter((l) => l.project_id === projectId);
    const summaryCards = [
      {
        kind: "lesson_plan" as const,
        title: "教案",
        status: summarize(lessons.map((l) => l.branches.lesson_plan.state)),
        preview_url: null,
        lesson_id: null,
      },
      {
        kind: "ppt" as const,
        title: "PPT",
        status: summarize(lessons.map((l) => l.branches.ppt.state)),
        preview_url: items.find((a) => a.kind === "ppt_page")?.preview_url ?? null,
        lesson_id: null,
      },
      {
        kind: "video" as const,
        title: "课堂导入视频",
        status: summarize(lessons.map((l) => l.branches.video.state)),
        preview_url: items.find((a) => a.kind === "video_clip")?.preview_url ?? null,
        lesson_id: null,
      },
    ];
    return ok(
      {
        items: items.map((a) => ({
          id: a.id,
          kind: a.kind,
          title: a.title,
          usage_label: a.usage_label,
          source_label: a.source_label,
          lesson_id: a.lesson_id,
          lesson_title: a.lesson_title,
          slot_key: a.slot_key,
          is_current: a.is_current,
          preview_url: a.preview_url,
          version_no: a.version_no,
          created_at: a.created_at,
        })),
        summary_cards: summaryCards,
      },
      { meta: { next_cursor: null } },
    );
  }),

  http.post(API("/asset-versions/:assetVersionId/download"), async ({ params }) => {
    await simulateLatency(130);
    const denied = requireSession();
    if (denied) return denied;
    const asset = db.assets.get(params.assetVersionId as string);
    if (!asset) return notFound("素材");
    return ok(
      {
        url: asset.preview_url ?? "data:text/plain,mock",
        expires_at: new Date(Date.now() + 10 * 60_000).toISOString(),
        file_name: `${asset.title}.png`,
      },
      { status: 201 },
    );
  }),

  // ── 交付 ─────────────────────────────────────────────
  http.get(API("/projects/:projectId/delivery"), async ({ params }) => {
    await simulateLatency(120);
    const denied = requireSession();
    if (denied) return denied;
    const projectId = params.projectId as string;
    const delivery = db.deliveries.get(projectId);
    if (!delivery) return notFound("交付");
    const lessons = [...db.lessons.values()]
      .filter((l) => l.project_id === projectId)
      .sort((a, b) => a.position - b.position);
    const readiness = lessons.flatMap((lesson) =>
      (Object.entries(lesson.branches) as [string, typeof lesson.branches.lesson_plan][])
        .map(([branchKey, branchState]) => ({
          branch: branchKey as "lesson_plan" | "intro_options" | "ppt" | "video",
          label: `${lesson.title} · ${branchLabel(branchKey)}`,
          state: mapBranchToReadiness(branchState.state),
          lesson_id: lesson.id,
          lesson_title: lesson.title,
          blockers:
            branchState.state === "review_required" || branchState.state === "in_progress"
              ? [branchState.summary ?? "仍在制作中"]
              : [],
        }))
        .filter((entry) => entry.state !== "disabled"),
    );
    const allApproved = readiness.every((r) => r.state === "approved" || r.state === "skipped");
    const status = delivery.package ? delivery.status : allApproved ? "ready" : "not_ready";
    return ok({ status, readiness, package: delivery.package });
  }),

  http.post(API("/projects/:projectId/delivery/package"), async ({ params, request }) => {
    await simulateLatency(200);
    const denied = requireSession();
    if (denied) return denied;
    const projectId = params.projectId as string;
    const delivery = db.deliveries.get(projectId);
    const project = db.projects.get(projectId);
    if (!delivery || !project) return notFound("交付");
    return idempotent(request, `package:${projectId}:${delivery.package?.version_no ?? 0}`, () => {
      delivery.status = "packaging";
      const job = startJob({
        kind: "delivery_package",
        title: `打包交付：${project.title}`,
        projectId,
        phaseMs: [800, 2600],
        onComplete: () => {
          delivery.status = "packaged";
          delivery.package = {
            version_no: (delivery.package?.version_no ?? 0) + 1,
            created_at: nowIso(),
            files: [
              { file_key: "plan-docx", title: "教案（DOCX）", kind: "docx", size_bytes: 128_400, asset_version_id: null },
              { file_key: "plan-pdf", title: "教案（PDF）", kind: "pdf", size_bytes: 96_300, asset_version_id: null },
              { file_key: "ppt", title: "课堂PPT（可编辑）", kind: "pptx", size_bytes: 2_356_000, asset_version_id: null },
              { file_key: "video", title: "课堂导入视频（MP4）", kind: "mp4", size_bytes: 18_204_000, asset_version_id: null },
              { file_key: "subtitle", title: "字幕（SRT）", kind: "srt", size_bytes: 4_200, asset_version_id: null },
              { file_key: "report", title: "生成说明与素材清单", kind: "report", size_bytes: 22_100, asset_version_id: null },
            ],
          };
          emitEvent({
            event_type: "delivery.packaged",
            project_id: projectId,
            resource: { type: "delivery", id: projectId },
          });
        },
      });
      return {
        data: { job_id: job.id, status: "queued" as const, events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
        status: 202,
      };
    });
  }),

  // ── 预算与自动化 ─────────────────────────────────────
  http.post(API("/projects/:projectId/budget-authorizations"), async ({ params, request }) => {
    await simulateLatency(160);
    const denied = requireSession();
    if (denied) return denied;
    const automation = db.automations.get(params.projectId as string);
    if (!automation) return notFound("项目");
    const body = (await request.json()) as { max_minor_units?: number; reason?: string | null };
    if (body.max_minor_units === undefined || body.max_minor_units < 0) {
      return fail(422, "VALIDATION_FAILED", "请输入有效的费用上限。");
    }
    return idempotent(request, `budget:${params.projectId}:${body.max_minor_units}`, () => {
      return {
        data: {
          budget_authorization_id: nextId(),
          max_minor_units: body.max_minor_units!,
          currency: "CNY",
          created_at: nowIso(),
        },
        status: 201,
      };
    });
  }),

  http.post(API("/projects/:projectId/automation/resume"), async ({ params, request }) => {
    await simulateLatency(160);
    const denied = requireSession();
    if (denied) return denied;
    const projectId = params.projectId as string;
    const automation = db.automations.get(projectId);
    const project = db.projects.get(projectId);
    if (!automation || !project) return notFound("项目");
    if (automation.state !== "paused") {
      return fail(409, "AUTOMATION_NOT_PAUSED", "自动执行未处于暂停状态。");
    }
    return idempotent(request, `resume:${projectId}:${automation.paused_reason}`, () => {
      automation.state = "running";
      automation.paused_reason = null;
      automation.paused_detail = null;
      const estimate = automation.pending_estimate;
      automation.pending_estimate = null;
      const job = startJob({
        kind: "automation_resume",
        title: `继续自动执行：${project.title}`,
        projectId,
        totalItems: 12,
        phaseMs: [800, 3200],
        onComplete: (finished) => {
          automation.state = "idle";
          automation.spent_minor_units =
            (automation.spent_minor_units ?? 0) + (estimate?.minor_units ?? 0);
          finished.completed_items = finished.total_items;
          emitEvent({
            event_type: "automation.completed",
            project_id: projectId,
            resource: { type: "automation", id: projectId },
          });
        },
      });
      emitEvent({
        event_type: "automation.resumed",
        project_id: projectId,
        resource: { type: "automation", id: projectId },
      });
      return {
        data: { job_id: job.id, status: "queued" as const, events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
        status: 202,
      };
    });
  }),
];

function summarize(states: string[]): string {
  const active = states.filter((s) => s !== "disabled" && s !== "skipped");
  if (active.length === 0) return "未启用";
  if (active.every((s) => s === "approved")) return "全部完成";
  const done = active.filter((s) => s === "approved").length;
  return `${done}/${active.length} 完成`;
}

function branchLabel(key: string): string {
  const map: Record<string, string> = {
    lesson_plan: "教案",
    intro_options: "课堂导入方案",
    ppt: "PPT",
    video: "导入视频",
  };
  return map[key] ?? key;
}

function mapBranchToReadiness(
  state: string,
): "approved" | "pending" | "blocked" | "disabled" | "skipped" {
  switch (state) {
    case "approved":
      return "approved";
    case "disabled":
      return "disabled";
    case "skipped":
      return "skipped";
    case "failed":
      return "blocked";
    default:
      return "pending";
  }
}

/**
 * SSE 响应：先回放 Last-Event-ID 之后的事件，再持续推送新事件与心跳。
 * sse_recovery 场景（scenarios.ts）会在连接约 6 秒后强制断流。
 */
function sseResponse(request: Request, filter: (event: (typeof db.events)[number]) => boolean): Response {
  const url = new URL(request.url);
  const lastEventId =
    request.headers.get("Last-Event-ID") ?? url.searchParams.get("last_event_id");
  let cursorSeq = 0;
  if (lastEventId) {
    const found = db.events.find((e) => e.event_id === lastEventId);
    if (found) cursorSeq = found.sequence_no;
  }
  const shouldDrop = db.scenario === "sse_recovery";

  const stream = new ReadableStream({
    start(controller) {
      const encoder = new TextEncoder();
      const send = (event: (typeof db.events)[number]) => {
        controller.enqueue(
          encoder.encode(`id: ${event.event_id}\nevent: ${event.event_type}\ndata: ${JSON.stringify(event)}\n\n`),
        );
      };
      // 回放
      for (const event of db.events) {
        if (event.sequence_no > cursorSeq && filter(event)) {
          send(event);
          cursorSeq = event.sequence_no;
        }
      }
      const poll = setInterval(() => {
        for (const event of db.events) {
          if (event.sequence_no > cursorSeq && filter(event)) {
            send(event);
            cursorSeq = event.sequence_no;
          }
        }
      }, 250);
      const heartbeat = setInterval(() => {
        controller.enqueue(encoder.encode(`: heartbeat ${Date.now()}\n\n`));
      }, 5000);
      const cleanup = () => {
        clearInterval(poll);
        clearInterval(heartbeat);
        try {
          controller.close();
        } catch {
          // already closed
        }
      };
      if (shouldDrop) {
        setTimeout(cleanup, 6000 * db.speedFactor);
      }
      request.signal.addEventListener("abort", cleanup);
    },
  });
  return new HttpResponse(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}

