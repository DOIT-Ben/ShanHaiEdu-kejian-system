import { http } from "msw";
import { db, emitEvent, nextId, nowIso, touchLesson } from "../db";
import { API, checkIfMatch, fail, idempotent, notFound, ok, requireSession, simulateLatency } from "../http";
import { startJob } from "../engine";
import { placeholderSvg } from "../seed";
import { validatePageCanvas, type PptPageSpec } from "@/entities/content/pptPage";

function pagePayload(page: NonNullable<ReturnType<typeof db.pptPages.get>>) {
  return {
    page_id: page.page_id,
    page_key: page.spec.page_key,
    position: page.spec.position,
    page_type: page.spec.page_type,
    status: page.status,
    teaching_task: page.spec.teaching_task,
    preview_url: page.preview_url,
    is_stale: page.is_stale,
    stale_reason: page.stale_reason,
  };
}

/** PPT 页级：清单、单页读写、单页重生成、视觉合同（封面门禁）。 */
export const pptHandlers = [
  http.get(API("/lessons/:lessonId/ppt-pages"), async ({ params }) => {
    await simulateLatency(120);
    const denied = requireSession();
    if (denied) return denied;
    const lessonId = params.lessonId as string;
    if (!db.lessons.get(lessonId)) return notFound("课时");
    const items = [...db.pptPages.values()]
      .filter((page) => page.lesson_id === lessonId)
      .sort((a, b) => a.spec.position - b.spec.position)
      .map(pagePayload);
    return ok({ items });
  }),

  http.get(API("/ppt-pages/:pageId"), async ({ params }) => {
    await simulateLatency(100);
    const denied = requireSession();
    if (denied) return denied;
    const page = db.pptPages.get(params.pageId as string);
    if (!page) return notFound("页面");
    return ok(
      { page: pagePayload(page), spec: page.spec, asset_slots: page.asset_slots },
      { etag: page.etag },
    );
  }),

  http.put(API("/ppt-pages/:pageId"), async ({ params, request }) => {
    await simulateLatency(160);
    const denied = requireSession();
    if (denied) return denied;
    const page = db.pptPages.get(params.pageId as string);
    if (!page) return notFound("页面");
    const conflict = checkIfMatch(request, page.etag);
    if (conflict) return conflict;
    const body = (await request.json()) as { spec?: PptPageSpec };
    if (!body.spec) return fail(422, "VALIDATION_FAILED", "缺少页面内容。");
    const canvasIssue = validatePageCanvas(body.spec);
    if (canvasIssue) {
      return fail(422, "CANVAS_RULE_VIOLATION", canvasIssue, {
        details: { field_errors: { canvas: canvasIssue } },
      });
    }
    page.spec = body.spec;
    page.etag += 1;
    if (page.status === "approved") page.status = "review_required";
    emitEvent({
      event_type: "ppt_page.updated",
      project_id: db.lessons.get(page.lesson_id)?.project_id ?? null,
      resource: { type: "ppt_page", id: page.page_id },
    });
    return ok(
      { page: pagePayload(page), spec: page.spec, asset_slots: page.asset_slots },
      { etag: page.etag },
    );
  }),

  http.post(API("/ppt-pages/:pageId/regenerate"), async ({ params, request }) => {
    await simulateLatency(150);
    const denied = requireSession();
    if (denied) return denied;
    const page = db.pptPages.get(params.pageId as string);
    if (!page) return notFound("页面");
    const lesson = db.lessons.get(page.lesson_id);
    if (!lesson) return notFound("课时");
    // 正文页生成前必须存在视觉合同（封面门禁）
    const contract = [...db.styleContracts.values()].find((c) => c.lesson_id === page.lesson_id);
    if (page.spec.page_type !== "cover" && !contract) {
      return fail(409, "COVER_NOT_APPROVED", "请先确定封面风格，再制作正文页面。");
    }
    const body = (await request.json().catch(() => ({}))) as { instruction?: string | null } | null;
    return idempotent(request, `page-regen:${page.page_id}:${body?.instruction ?? ""}`, () => {
      page.status = "generating";
      const job = startJob({
        kind: "ppt_page",
        title: `重新生成 第${page.spec.position}页`,
        projectId: lesson.project_id,
        lessonId: lesson.id,
        phaseMs: [700, 2400],
        onComplete: () => {
          page.status = "review_required";
          page.preview_url = placeholderSvg(`${page.spec.page_key} 新预览`, "#315ef5");
          page.is_stale = false;
          page.stale_reason = null;
          for (const slot of page.asset_slots) {
            slot.status = "filled";
            slot.asset_version_id = slot.asset_version_id ?? nextId();
            slot.preview_url = placeholderSvg(`${slot.slot_key}`, "#2449d8");
          }
          emitEvent({
            event_type: "ppt_page.generated",
            project_id: lesson.project_id,
            resource: { type: "ppt_page", id: page.page_id },
          });
        },
      });
      return {
        data: { job_id: job.id, status: "queued", events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
        status: 202,
      };
    });
  }),

  http.get(API("/lessons/:lessonId/ppt-style-contract"), async ({ params }) => {
    await simulateLatency(90);
    const denied = requireSession();
    if (denied) return denied;
    const lessonId = params.lessonId as string;
    if (!db.lessons.get(lessonId)) return notFound("课时");
    const contract = [...db.styleContracts.values()].find((c) => c.lesson_id === lessonId);
    if (!contract) return ok(null);
    return ok({
      id: contract.id,
      source_cover_result_id: contract.source_cover_result_id,
      summary: contract.summary,
      rules: contract.rules,
      cover_preview_url: contract.cover_preview_url,
      created_at: contract.created_at,
    });
  }),
];

/** 封面候选被采用并保存 → 生成视觉合同、解锁正文（由 save/adopt handler 调用）。 */
export function adoptCoverResult(lessonId: string, resultId: string): void {
  const result = db.results.get(resultId);
  const lesson = db.lessons.get(lessonId);
  if (!result || !lesson) return;
  result.review_state = "adopted";
  const contractId = nextId();
  db.styleContracts.set(contractId, {
    id: contractId,
    lesson_id: lessonId,
    source_cover_result_id: resultId,
    summary: "封面视觉语言：纸艺质感 · 暖光 · 山海蓝点缀 · 大面积留白",
    rules: {
      medium: "手工纸艺插画",
      palette: ["#315EF5", "#E8B04B", "#F5F7FB"],
      lighting: "柔和暖光",
      composition: "主视觉居中偏左，右侧留白排版",
      forbidden: ["文字烘焙进图片", "写实摄影", "重彩渐变"],
    },
    cover_preview_url: result.preview_url,
    created_at: nowIso(),
  });
  // 封面节点批准、正文节点就绪
  for (const run of db.nodeRuns.values()) {
    if (run.lesson_id !== lessonId) continue;
    if (run.node_key === "ppt_cover") {
      run.status = "approved";
      run.updated_at = nowIso();
    }
    if (run.node_key === "ppt_body" && run.status === "not_ready") {
      run.status = "ready";
      run.updated_at = nowIso();
    }
  }
  lesson.branches.ppt = { state: "in_progress", summary: "封面已定，可制作正文", next_step_key: "ppt-body" };
  touchLesson(lessonId);
  emitEvent({
    event_type: "ppt_style_contract.created",
    project_id: lesson.project_id,
    resource: { type: "ppt_style_contract", id: contractId },
  });
}
