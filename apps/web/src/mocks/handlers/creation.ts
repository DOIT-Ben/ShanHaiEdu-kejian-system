import { http } from "msw";
import { db, emitEvent, nextId, nowIso } from "../db";
import { API, checkIfMatch, fail, idempotent, notFound, ok, requireSession, simulateLatency } from "../http";
import { startJob, produceResults } from "../engine";
import { adoptCoverResult } from "./ppt";

function batchPayload(batch: NonNullable<ReturnType<typeof db.batches.get>>) {
  return {
    id: batch.id,
    studio_type: batch.studio_type,
    title: batch.title,
    status: batch.status,
    creation_package_id: batch.creation_package_id,
    source_project_id: batch.source_project_id,
    source_project_title: batch.source_project_title,
    default_save_target: batch.default_save_target,
    style_contract: batch.style_contract,
    items: batch.items,
    active_job_id: batch.active_job_id,
    created_at: batch.created_at,
    updated_at: batch.updated_at,
  };
}

/** 通用创作中心：创作包、批次、生成、候选、保存到项目、下载。 */
export const creationHandlers = [
  http.post(API("/node-runs/:nodeRunId/creation-packages"), async ({ params, request }) => {
    await simulateLatency(180);
    const denied = requireSession();
    if (denied) return denied;
    const run = db.nodeRuns.get(params.nodeRunId as string);
    if (!run) return notFound("步骤");
    const existing = [...db.packages.values()].find((p) => p.source.node_run_id === run.id);
    return idempotent(request, `package:${run.id}`, () => {
      if (existing) return { data: existing, status: 201 };
      const packageId = nextId();
      const pkg = {
        package_id: packageId,
        package_type: "image" as const,
        status: "ready" as const,
        source: {
          project_id: run.project_id,
          lesson_unit_id: run.lesson_id,
          node_run_id: run.id,
          is_stale: false,
        },
        style_contract: null,
        items: [
          {
            item_key: "ITEM-01",
            position: 1,
            title: `${run.title}素材`,
            prompt: { description: `${run.title}相关素材` },
            output_spec: { media_type: "image", count: 2 },
            target_slot_key: null,
            consistency_key: null,
          },
        ],
        target_rules: { default_project_id: run.project_id },
        created_at: nowIso(),
      };
      db.packages.set(packageId, pkg);
      return { data: pkg, status: 201 };
    });
  }),

  http.get(API("/creation-packages/:packageId"), async ({ params }) => {
    await simulateLatency(100);
    const denied = requireSession();
    if (denied) return denied;
    const pkg = db.packages.get(params.packageId as string);
    if (!pkg) return notFound("待生成内容");
    return ok(pkg);
  }),

  http.get(API("/creation-batches"), async ({ request }) => {
    await simulateLatency(120);
    const denied = requireSession();
    if (denied) return denied;
    const url = new URL(request.url);
    const studioType = url.searchParams.get("studio_type");
    const items = [...db.batches.values()]
      .filter((b) => !studioType || b.studio_type === studioType)
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .map(batchPayload);
    return ok({ items }, { meta: { next_cursor: null } });
  }),

  http.post(API("/creation-batches"), async ({ request }) => {
    await simulateLatency(180);
    const denied = requireSession();
    if (denied) return denied;
    const body = (await request.json()) as {
      studio_type?: "image" | "video" | "presentation";
      title?: string;
      creation_package_id?: string | null;
    };
    if (!body.studio_type || !body.title) {
      return fail(422, "VALIDATION_FAILED", "缺少创作类型或标题。");
    }
    return idempotent(request, `batch:${body.studio_type}:${body.title}:${body.creation_package_id ?? ""}`, () => {
      const id = nextId();
      const now = nowIso();
      let items: NonNullable<ReturnType<typeof db.batches.get>>["items"] = [];
      let sourceProject: string | null = null;
      let sourceTitle: string | null = null;
      let styleContract: Record<string, unknown> | null = null;
      let defaultTarget: string | null = null;
      if (body.creation_package_id) {
        const pkg = db.packages.get(body.creation_package_id);
        if (!pkg) return notFound("待生成内容");
        if (pkg.status !== "ready") {
          return fail(409, "PACKAGE_NOT_READY", "待生成内容尚未就绪或已失效。");
        }
        sourceProject = pkg.source.project_id;
        sourceTitle = db.projects.get(pkg.source.project_id)?.title ?? null;
        styleContract = pkg.style_contract;
        defaultTarget = (pkg.target_rules as { default_save_target?: string }).default_save_target ?? null;
        items = pkg.items.map((item) => ({
          id: nextId(),
          item_key: item.item_key,
          position: item.position,
          title: item.title,
          status: "ready" as const,
          prompt: item.prompt,
          output_spec: item.output_spec,
          reference_assets: (item.reference_assets ?? []).map((ref) => ({ ...ref, preview_url: null })),
          target_slot_key: item.target_slot_key ?? null,
          consistency_key: item.consistency_key ?? null,
          adopted_result_id: null,
          saved_binding_id: null,
        }));
      } else {
        items = [
          {
            id: nextId(),
            item_key: "ITEM-01",
            position: 1,
            title: body.title!,
            status: "draft" as const,
            prompt: { description: "" },
            output_spec: { media_type: body.studio_type === "presentation" ? "ppt_page" : body.studio_type, count: body.studio_type === "video" ? 2 : 4 },
            reference_assets: [],
            target_slot_key: null,
            consistency_key: null,
            adopted_result_id: null,
            saved_binding_id: null,
          },
        ];
      }
      const batch = {
        id,
        studio_type: body.studio_type!,
        title: body.title!,
        status: "draft" as const,
        creation_package_id: body.creation_package_id ?? null,
        source_project_id: sourceProject,
        source_project_title: sourceTitle,
        default_save_target: defaultTarget,
        style_contract: styleContract,
        items,
        active_job_id: null,
        created_at: now,
        updated_at: now,
        etag: 1,
      };
      db.batches.set(id, batch);
      return { data: batchPayload(batch), status: 201 };
    });
  }),

  http.get(API("/creation-batches/:batchId"), async ({ params }) => {
    await simulateLatency(100);
    const denied = requireSession();
    if (denied) return denied;
    const batch = db.batches.get(params.batchId as string);
    if (!batch) return notFound("本次创作");
    return ok(batchPayload(batch), { etag: batch.etag });
  }),

  http.patch(API("/creation-batches/:batchId/items/:itemKey"), async ({ params, request }) => {
    await simulateLatency(140);
    const denied = requireSession();
    if (denied) return denied;
    const batch = db.batches.get(params.batchId as string);
    if (!batch) return notFound("本次创作");
    const conflict = checkIfMatch(request, batch.etag);
    if (conflict) return conflict;
    const item = batch.items.find((i) => i.item_key === params.itemKey);
    if (!item) return notFound("创作项");
    const body = (await request.json()) as Partial<{
      title: string;
      prompt: Record<string, unknown>;
      output_spec: Record<string, unknown>;
      reference_assets: { asset_version_id: string; role: string }[];
    }>;
    if (body.title !== undefined) item.title = body.title;
    if (body.prompt !== undefined) item.prompt = body.prompt;
    if (body.output_spec !== undefined) item.output_spec = body.output_spec;
    if (body.reference_assets !== undefined) {
      item.reference_assets = body.reference_assets.map((ref) => ({ ...ref, preview_url: null }));
    }
    if (item.status === "draft" && (item.prompt as { description?: string }).description) {
      item.status = "ready";
    }
    batch.etag += 1;
    batch.updated_at = nowIso();
    return ok(batchPayload(batch), { etag: batch.etag });
  }),

  http.post(API("/creation-batches/:batchId/generate"), async ({ params, request }) => {
    await simulateLatency(180);
    const denied = requireSession();
    if (denied) return denied;
    const batch = db.batches.get(params.batchId as string);
    if (!batch) return notFound("本次创作");
    const body = (await request.json()) as { item_ids?: string[] };
    if (!body.item_ids?.length) {
      return fail(422, "VALIDATION_FAILED", "请选择要生成的内容。");
    }
    const targets = batch.items.filter((item) => body.item_ids!.includes(item.id));
    if (targets.length === 0) return notFound("创作项");
    const notReady = targets.find((item) => !(item.prompt as { description?: string }).description);
    if (notReady) {
      return fail(409, "ITEM_NOT_READY", `「${notReady.title}」还没有填写生成要求。`);
    }
    return idempotent(request, `batch-gen:${batch.id}:${[...body.item_ids].sort().join(",")}`, () => {
      for (const item of targets) item.status = "queued";
      batch.status = "running";
      batch.updated_at = nowIso();
      const job = startJob({
        kind: `creation_${batch.studio_type}`,
        title: `${batch.title}：生成 ${targets.length} 项`,
        projectId: batch.source_project_id,
        batchId: batch.id,
        totalItems: targets.length,
        phaseMs: [800, 2800],
        onComplete: (finished) => {
          for (const item of targets) {
            item.status = "review_required";
            produceResults({
              batchId: batch.id,
              itemKey: item.item_key,
              mediaType: batch.studio_type === "video" ? "video" : "image",
              count: (item.output_spec as { count?: number }).count ?? 2,
              labelPrefix: item.title,
              durationSeconds: batch.studio_type === "video" ? 10 : null,
            });
          }
          batch.status = batch.items.every((i) => i.status === "saved" || i.status === "adopted" || i.status === "review_required")
            ? "partially_completed"
            : "partially_completed";
          batch.active_job_id = null;
          batch.updated_at = nowIso();
          emitEvent({
            event_type: "creation_batch.results_ready",
            project_id: batch.source_project_id,
            resource: { type: "creation_batch", id: batch.id },
            payload: { job_id: finished.id },
          });
        },
      });
      batch.active_job_id = job.id;
      return {
        data: { job_id: job.id, status: "queued", events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
        status: 202,
      };
    });
  }),

  http.get(API("/creation-batches/:batchId/results"), async ({ params, request }) => {
    await simulateLatency(110);
    const denied = requireSession();
    if (denied) return denied;
    const batchId = params.batchId as string;
    if (!db.batches.get(batchId)) return notFound("本次创作");
    const url = new URL(request.url);
    const itemKey = url.searchParams.get("item_key");
    const items = [...db.results.values()]
      .filter((r) => r.batch_id === batchId && (!itemKey || r.item_key === itemKey))
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    return ok({ items });
  }),

  // ── 保存到项目（原子操作 + 槽位冲突） ────────────────
  http.post(API("/generation-results/:resultId/save-to-project"), async ({ params, request }) => {
    await simulateLatency(220);
    const denied = requireSession();
    if (denied) return denied;
    const result = db.results.get(params.resultId as string);
    if (!result) return notFound("候选结果");
    const body = (await request.json()) as {
      project_id?: string;
      slot_key?: string;
      replace_mode?: "reject_if_occupied" | "replace_active" | "append";
    };
    if (!body.project_id || !body.slot_key || !body.replace_mode) {
      return fail(422, "VALIDATION_FAILED", "缺少保存目标信息。");
    }
    const project = db.projects.get(body.project_id);
    if (!project) return notFound("项目");

    const occupied = [...db.assets.values()].find(
      (a) => a.project_id === body.project_id && a.slot_key === body.slot_key && a.is_current,
    );
    if (occupied && body.replace_mode === "reject_if_occupied") {
      return fail(409, "SLOT_OCCUPIED", "目标位置已有内容，请选择替换、另存或仅下载。", {
        details: {
          occupied_by: { asset_version_id: occupied.id, title: occupied.title, version_no: occupied.version_no },
        },
      });
    }

    return idempotent(request, `save:${result.id}:${body.project_id}:${body.slot_key}:${body.replace_mode}`, () => {
      const bindingId = nextId();
      const now = nowIso();
      let versionNo = 1;
      if (occupied && body.replace_mode === "replace_active") {
        occupied.is_current = false;
        versionNo = occupied.version_no + 1;
      }
      if (occupied && body.replace_mode === "append") {
        versionNo = Math.max(...[...db.assets.values()].filter((a) => a.slot_key === body.slot_key).map((a) => a.version_no)) + 1;
      }
      const assetId = nextId();
      const batch = result.batch_id ? db.batches.get(result.batch_id) : null;
      const item = batch?.items.find((i) => i.item_key === result.item_key) ?? null;
      db.assets.set(assetId, {
        id: assetId,
        project_id: body.project_id!,
        kind: result.media_type === "video" ? "video_clip" : result.media_type === "ppt_page" ? "ppt_page" : "image",
        title: item?.title ?? result.item_key,
        usage_label: body.slot_key!.startsWith("video.") ? "视频素材" : body.slot_key!.startsWith("ppt.") ? "PPT 素材" : "教学素材",
        source_label: batch ? `来自「${batch.title}」` : "生成后保存",
        lesson_id: null,
        lesson_title: null,
        slot_key: body.slot_key!,
        is_current: body.replace_mode !== "append" || !occupied,
        preview_url: result.preview_url,
        version_no: versionNo,
        created_at: now,
      });
      result.review_state = "adopted";
      result.saved_binding_id = bindingId;
      let clipId: string | null = null;

      // 视频镜头候选：保存成功才产生 clip_id
      const shot = [...db.shots.values()].find((s) => s.shot_key === result.item_key && result.node_run_id != null);
      if (shot && result.media_type === "video") {
        clipId = nextId();
        shot.current_clip = {
          clip_id: clipId,
          result_id: result.id,
          preview_url: result.preview_url,
          saved_at: now,
        };
        shot.status = "adopted";
        shot.failure_reason = null;
        // 全部镜头就绪 → 合成节点 ready
        const vp = db.videoProjects.get(shot.video_project_id);
        if (vp) {
          const allAdopted = [...db.shots.values()]
            .filter((s) => s.video_project_id === vp.id)
            .every((s) => s.status === "adopted");
          if (allAdopted) {
            for (const run of db.nodeRuns.values()) {
              if (run.lesson_id === vp.lesson_id && run.node_key === "video_compose" && run.status === "not_ready") {
                run.status = "ready";
                run.updated_at = now;
              }
              if (run.lesson_id === vp.lesson_id && run.node_key === "video_clips") {
                run.status = "approved";
                run.updated_at = now;
              }
            }
          }
        }
      }

      // 封面候选保存 → 视觉合同 + 正文解锁
      if (result.node_run_id) {
        const run = db.nodeRuns.get(result.node_run_id);
        if (run?.node_key === "ppt_cover" && run.lesson_id && body.slot_key === "ppt.cover.main_visual") {
          adoptCoverResult(run.lesson_id, result.id);
        }
      }

      if (item) {
        item.status = "saved";
        item.adopted_result_id = result.id;
        item.saved_binding_id = bindingId;
        if (batch) {
          batch.updated_at = now;
          batch.etag += 1;
          if (batch.items.every((i) => i.status === "saved")) batch.status = "completed";
        }
      }

      db.auditEvents.unshift({
        id: nextId(),
        actor_name: db.users.find((u) => u.id === db.sessionUserId)?.name ?? "未知用户",
        action: "save_to_project.execute",
        resource_label: `${item?.title ?? result.item_key} → ${project.title}`,
        detail: `slot=${body.slot_key} mode=${body.replace_mode}`,
        occurred_at: now,
      });
      emitEvent({
        event_type: "asset.saved",
        project_id: body.project_id,
        resource: { type: "asset_version", id: assetId },
        payload: { slot_key: body.slot_key },
      });
      return {
        data: {
          operation_id: nextId(),
          status: "completed" as const,
          binding_id: bindingId,
          clip_id: clipId,
          saved_to: {
            project_id: body.project_id!,
            project_title: project.title,
            slot_key: body.slot_key!,
            slot_label: item?.title ?? body.slot_key!,
          },
        },
      };
    });
  }),

  http.post(API("/generation-results/:resultId/download"), async ({ params }) => {
    await simulateLatency(150);
    const denied = requireSession();
    if (denied) return denied;
    const result = db.results.get(params.resultId as string);
    if (!result) return notFound("候选结果");
    return ok(
      {
        url: result.preview_url ?? "data:text/plain,mock",
        expires_at: new Date(Date.now() + 10 * 60_000).toISOString(),
        file_name: `${result.item_key}.${result.media_type === "video" ? "mp4" : "png"}`,
      },
      { status: 201 },
    );
  }),
];
