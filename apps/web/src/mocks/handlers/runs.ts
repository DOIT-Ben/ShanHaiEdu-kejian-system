import { http } from "msw";
import type { CostEstimate, PromptVersion } from "@/shared/api/types";
import { getNodeDef } from "@/entities/workflow/nodes";
import { getDb, minutesAgo, nextId } from "../db";
import { publishEvent } from "../events";
import { startNodeRun, startTask } from "../engine";
import { makePromptVersion, promptTextForNode } from "../fixtures/prompts";
import { makeArtifact } from "../fixtures/projects";
import { registerGeneratedAsset } from "../generation";
import type { ClipsContent, ImageAssetsContent, IntroDesignContent, PptPagesContent } from "@/entities/content";
import { api, fail, guard, ok, simulateLatency } from "./http";
import { findLesson } from "./lessons";

/** 节点预计费用（分）。 */
function estimateCostMinor(nodeKey: string): { min: number; max: number; candidates: number } {
  switch (nodeKey) {
    case "ppt_assets":
      return { min: 240, max: 480, candidates: 3 };
    case "video_master_image":
      return { min: 360, max: 480, candidates: 3 };
    case "video_image_assets":
      return { min: 960, max: 1280, candidates: 8 };
    case "video_clips":
      return { min: 12_000, max: 16_000, candidates: 8 };
    case "video_audio_subtitle":
      return { min: 60, max: 100, candidates: 1 };
    case "video_final_cut":
      return { min: 200, max: 400, candidates: 1 };
    case "ppt_export":
      return { min: 0, max: 0, candidates: 1 };
    default:
      return { min: 60, max: 120, candidates: 1 };
  }
}

function routeInfoFor(nodeKey: string): { businessModelName: string; providerName: string; allowFallback: boolean } {
  const db = getDb();
  const capability = getNodeDef(nodeKey)?.capability;
  const route = db.routes.find((r) => r.capability === capability && r.enabled);
  const model = db.models.find((m) => m.model_id === route?.primary_model_id);
  return {
    businessModelName: model?.business_name ?? "推荐模型",
    providerName: model?.provider_name ?? "平台网关",
    allowFallback: route?.allow_cross_provider_fallback ?? false,
  };
}

export const runHandlers = [
  // ---------- 提示词草稿 ----------
  http.post(api("/lessons/:lessonId/nodes/:nodeKey/prompt-drafts"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const found = findLesson(db, String(params.lessonId));
    const nodeKey = String(params.nodeKey);
    const node = found?.lessonState.nodes.get(nodeKey);
    if (!found || !node) return fail(404, "NOT_FOUND", "节点不存在。");
    const body = (await request.json()) as {
      input_values?: Record<string, unknown>;
      revision_instruction?: string;
      base_prompt_version_id?: string;
      edited_prompt?: string;
      reset_to_default?: boolean;
    };
    const latest = node.promptVersions[0];
    const base = body.base_prompt_version_id
      ? node.promptVersions.find((p) => p.prompt_version_id === body.base_prompt_version_id) ?? latest
      : latest;
    const versionNumber = (latest?.version_number ?? 0) + 1;
    let editablePrompt: string;
    let source: PromptVersion["source"] = "system";
    if (body.reset_to_default) {
      editablePrompt = promptTextForNode(nodeKey);
      source = "system";
    } else if (body.edited_prompt !== undefined) {
      editablePrompt = body.edited_prompt;
      source = "edited";
    } else if (body.revision_instruction) {
      editablePrompt = `${base?.editable_prompt ?? promptTextForNode(nodeKey)}\n\n【本次修改要求】\n${body.revision_instruction}`;
      source = "revision";
    } else {
      editablePrompt = base?.editable_prompt ?? promptTextForNode(nodeKey);
      source = base?.source ?? "system";
    }
    if (body.input_values) {
      node.inputValues = { ...node.inputValues, ...body.input_values };
    }
    const version = makePromptVersion({
      nodeKey,
      versionNumber,
      source,
      editablePrompt,
      basePromptVersionId: base?.prompt_version_id ?? null,
      createdMinutesAgo: 0,
    });
    if (body.revision_instruction) {
      db.fileNames.set(`revision:${version.prompt_version_id}`, body.revision_instruction);
    }
    node.promptVersions.unshift(version);
    return ok(version, { status: 201 });
  }),

  // ---------- 费用预估 ----------
  http.post(api("/lessons/:lessonId/nodes/:nodeKey/cost-estimate"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const found = findLesson(db, String(params.lessonId));
    const nodeKey = String(params.nodeKey);
    if (!found) return fail(404, "NOT_FOUND", "课时不存在。");
    const est = estimateCostMinor(nodeKey);
    const route = routeInfoFor(nodeKey);
    const project = found.project.project;
    const remaining = (project.budget_minor_units ?? 0) - (project.spent_minor_units ?? 0);
    const requiresAuth = Boolean(db.flags.budgetAuthRequired) && est.max > remaining;
    const estimate: CostEstimate = {
      currency: "CNY",
      minimum_minor_units: est.min,
      maximum_minor_units: est.max,
      candidate_count: est.candidates,
      requires_authorization: requiresAuth,
      business_model_name: route.businessModelName,
      provider_name: route.providerName,
      allow_fallback: route.allowFallback,
      parameter_summary: {
        budget_remaining_minor_units: remaining,
        authorization_reason: requiresAuth
          ? `预计费用上限 ¥${(est.max / 100).toFixed(2)} 超过项目剩余预算 ¥${(remaining / 100).toFixed(2)}，需要额外授权。`
          : null,
      },
    };
    return ok(estimate);
  }),

  // ---------- 预算授权 ----------
  http.post(api("/lessons/:lessonId/nodes/:nodeKey/budget-authorizations"), async ({ request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const body = (await request.json()) as { max_minor_units?: number; reason?: string };
    const authorization = {
      budget_authorization_id: nextId(db, "budgetauth"),
      max_minor_units: body.max_minor_units ?? 0,
      reason: body.reason ?? null,
      expires_at: minutesAgo(-30),
    };
    return ok(authorization, { status: 201 });
  }),

  // ---------- 节点运行 ----------
  http.post(api("/lessons/:lessonId/nodes/:nodeKey/runs"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const found = findLesson(db, String(params.lessonId));
    const nodeKey = String(params.nodeKey);
    const node = found?.lessonState.nodes.get(nodeKey);
    if (!found || !node) return fail(404, "NOT_FOUND", "节点不存在。");

    const idempotencyKey = request.headers.get("idempotency-key");
    if (!idempotencyKey || idempotencyKey.length < 16) {
      return fail(400, "IDEMPOTENCY_KEY_REQUIRED", "缺少幂等键，请刷新后重试。");
    }
    const idemKey = `run:${found.lessonState.lesson.lesson_id}:${nodeKey}:${idempotencyKey}`;
    if (db.idempotency.has(idemKey)) {
      const existing = db.tasks.get(db.idempotency.get(idemKey)!);
      if (existing) return ok(existing, { status: 202 });
    }

    const status = node.summary.status;
    if (status === "locked" || status === "blocked") {
      return fail(409, "NODE_LOCKED", node.summary.blocker_message ?? "上游步骤还未完成，暂时不能开始。", { action: "complete_upstream" });
    }
    if (status === "queued" || status === "running") {
      return fail(409, "NODE_BUSY", "该步骤已有生成任务在进行中。", { action: "view_task" });
    }

    const body = (await request.json()) as {
      prompt_version_id?: string;
      model_profile?: string;
      budget_authorization_id?: string;
      parameters?: Record<string, unknown>;
    };
    const est = estimateCostMinor(nodeKey);
    const project = found.project.project;
    const remaining = (project.budget_minor_units ?? 0) - (project.spent_minor_units ?? 0);
    if (db.flags.budgetAuthRequired && est.max > remaining && !body.budget_authorization_id) {
      return fail(403, "BUDGET_AUTHORIZATION_REQUIRED", "本次生成预计费用超过项目剩余预算，需要先授权。", {
        action: "authorize_budget",
        details: { estimated_max_minor_units: est.max, budget_remaining_minor_units: remaining },
      });
    }
    const route = routeInfoFor(nodeKey);
    const promptVersion = body.prompt_version_id
      ? node.promptVersions.find((p) => p.prompt_version_id === body.prompt_version_id)
      : node.promptVersions[0];
    const revisionInstruction = promptVersion
      ? db.fileNames.get(`revision:${promptVersion.prompt_version_id}`) ?? null
      : null;
    const task = startNodeRun({
      projectId: project.project_id,
      lessonId: found.lessonState.lesson.lesson_id,
      nodeKey,
      promptVersionId: promptVersion?.prompt_version_id ?? null,
      revisionInstruction,
      estimatedCostMinor: Math.round((est.min + est.max) / 2),
      providerName: route.providerName,
    });
    db.idempotency.set(idemKey, task.task_id);
    return ok(task, { status: 202 });
  }),

  // ---------- 教师直接编辑，创建新产物版本 ----------
  http.post(api("/lessons/:lessonId/nodes/:nodeKey/artifact-versions"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const found = findLesson(db, String(params.lessonId));
    const nodeKey = String(params.nodeKey);
    const node = found?.lessonState.nodes.get(nodeKey);
    if (!found || !node) return fail(404, "NOT_FOUND", "节点不存在。");
    const body = (await request.json()) as { content?: Record<string, unknown>; base_version_id?: string };
    if (!body.content) {
      return fail(422, "VALIDATION_FAILED", "缺少产物内容。", { details: { field_errors: { content: "内容不能为空" } } });
    }
    const versionNumber = node.artifactVersions.length > 0 ? Math.max(...node.artifactVersions.map((v) => v.version_number)) + 1 : 1;
    for (const version of node.artifactVersions) {
      if (version.status === "needs_review") version.status = "superseded";
    }
    const artifact = makeArtifact({
      artifactType: nodeKey,
      versionNumber,
      status: "needs_review",
      content: body.content,
      source: "edited",
      createdMinutesAgo: 0,
    });
    node.artifactVersions.unshift(artifact);
    node.summary.status = "needs_review";
    node.draftContent = null;
    publishEvent({ event_type: "artifact.version_created", project_id: found.project.project.project_id, lesson_id: found.lessonState.lesson.lesson_id, node_key: nodeKey, task_id: null, payload: { artifact_version_id: artifact.artifact_version_id, version_number: versionNumber } });
    return ok(artifact, { status: 201 });
  }),

  // ---------- 列表项级操作（单套/单页/单镜头/单片段） ----------
  http.post(api("/lessons/:lessonId/nodes/:nodeKey/items/:itemId/actions"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const found = findLesson(db, String(params.lessonId));
    const nodeKey = String(params.nodeKey);
    const itemId = String(params.itemId);
    const node = found?.lessonState.nodes.get(nodeKey);
    if (!found || !node) return fail(404, "NOT_FOUND", "节点不存在。");
    const latest = node.artifactVersions[0];
    if (!latest) return fail(409, "NO_ARTIFACT", "该步骤还没有产物。");
    const body = (await request.json()) as { action?: string; instruction?: string; payload?: Record<string, unknown> };
    const projectId = found.project.project.project_id;
    const lessonId = found.lessonState.lesson.lesson_id;

    const bumpVersion = (content: Record<string, unknown>, source: "generated" | "edited" = "edited") => {
      const versionNumber = Math.max(...node.artifactVersions.map((v) => v.version_number)) + 1;
      for (const version of node.artifactVersions) {
        if (version.status === "needs_review") version.status = "superseded";
      }
      const artifact = makeArtifact({ artifactType: nodeKey, versionNumber, status: "needs_review", content, source, createdMinutesAgo: 0 });
      node.artifactVersions.unshift(artifact);
      node.summary.status = "needs_review";
      publishEvent({ event_type: "artifact.version_created", project_id: projectId, lesson_id: lessonId, node_key: nodeKey, task_id: null, payload: { artifact_version_id: artifact.artifact_version_id, version_number: versionNumber } });
      return artifact;
    };

    switch (body.action) {
      // 批准一套导入方案 / 批准一个片段
      case "approve": {
        const content = structuredClone(latest.content) as Record<string, unknown>;
        if (nodeKey === "intro_design") {
          const intro = content as unknown as IntroDesignContent;
          let hit = false;
          for (const category of intro.categories) {
            for (const option of category.options) {
              if (option.option_id === itemId) {
                option.status = "approved";
                hit = true;
              }
            }
          }
          if (!hit) return fail(404, "NOT_FOUND", "方案不存在。");
          intro.selected_option_id = itemId;
          latest.content = content;
          return ok({ task: null, artifact_version: latest, node: node.summary });
        }
        return fail(422, "INVALID_ACTION", "该步骤不支持此操作。");
      }
      case "approve_clip": {
        const content = structuredClone(latest.content) as Record<string, unknown>;
        const clips = content as unknown as ClipsContent;
        const target = clips.clips.find((c) => c.clip_id === itemId);
        if (!target) return fail(404, "NOT_FOUND", "片段不存在。");
        for (const clip of clips.clips) {
          if (clip.shot_id === target.shot_id) {
            clip.status = clip.clip_id === itemId ? "approved" : clip.status === "approved" ? "completed" : clip.status;
          }
        }
        latest.content = content;
        const assetRecord = target.video_asset_id ? db.assets.get(target.video_asset_id) : null;
        if (assetRecord) {
          assetRecord.asset.status = "approved";
          assetRecord.versions[0].status = "approved";
        }
        return ok({ task: null, artifact_version: latest, node: node.summary });
      }
      // 单镜头片段重试（部分成功恢复）
      case "retry_clip": {
        const clips = latest.content as unknown as ClipsContent;
        const target = clips.clips.find((c) => c.clip_id === itemId);
        if (!target) return fail(404, "NOT_FOUND", "片段不存在。");
        const useFallback = Boolean(body.payload?.use_fallback_provider);
        if (db.flags.paidFallbackConfirm && !useFallback) {
          return fail(409, "PROVIDER_FALLBACK_CONFIRMATION_REQUIRED", "潮汐视频云仍不可用。该镜头已产生费用，切换到备用服务「星河视频」将再次计费，需要你的确认。", {
            action: "confirm_fallback",
            details: { fallback_provider_name: "星河视频（备用）", incurred_cost_minor_units: 1500, extra_cost_minor_units: 1800 },
          });
        }
        target.status = "generating";
        target.error_message = null;
        const task = startTask({
          taskType: "clip_retry",
          projectId,
          lessonId,
          nodeKey,
          itemId,
          durationMs: 7000,
          estimatedCostMinor: useFallback ? 1800 : 1500,
          actualCostMinor: useFallback ? 1800 : 1500,
          providerName: useFallback ? "星河视频（备用）" : "潮汐视频云",
          longPipeline: true,
          prevNodeStatus: node.summary.status,
          onComplete: () => {
            const current = node.artifactVersions[0];
            const content = structuredClone(current.content) as Record<string, unknown>;
            const currentClips = content as unknown as ClipsContent;
            const clip = currentClips.clips.find((c) => c.clip_id === itemId);
            if (clip) {
              const { assetId } = registerGeneratedAsset({ projectId, lessonId, assetType: "video", name: `镜头${clip.shot_no}片段（重试）`, sourceNodeKey: "video_clips", fileName: `clip_shot_${clip.shot_no}_retry.mp4`, mimeType: "video/mp4", sizeBytes: 6_200_000 });
              clip.status = "completed";
              clip.video_asset_id = assetId;
              clip.attempt += 1;
              clip.duration_seconds = clip.duration_seconds || 8;
              clip.error_message = null;
            }
            current.content = content;
            node.validationResults = node.validationResults.filter((v) => v.rule_id !== "all_clips_ready");
            publishEvent({ event_type: "artifact.version_created", project_id: projectId, lesson_id: lessonId, node_key: nodeKey, task_id: null, payload: { artifact_version_id: current.artifact_version_id, item_id: itemId } });
          },
        });
        return ok({ task, artifact_version: null, node: node.summary }, { status: 202 });
      }
      // 失败图片资产重试
      case "regenerate": {
        if (nodeKey === "video_image_assets") {
          const imageContent = latest.content as unknown as ImageAssetsContent;
          const target = imageContent.items.find((i) => i.image_id === itemId);
          if (!target) return fail(404, "NOT_FOUND", "图片项不存在。");
          target.status = "generating";
          target.error_message = null;
          const task = startTask({
            taskType: "image_retry",
            projectId,
            lessonId,
            nodeKey,
            itemId,
            durationMs: 5000,
            estimatedCostMinor: 120,
            actualCostMinor: 120,
            providerName: "绘山图像",
            prevNodeStatus: node.summary.status,
            onComplete: () => {
              const current = node.artifactVersions[0];
              const content = structuredClone(current.content) as Record<string, unknown>;
              const items = (content as unknown as ImageAssetsContent).items;
              const item = items.find((i) => i.image_id === itemId);
              if (item) {
                const { assetId } = registerGeneratedAsset({ projectId, lessonId, assetType: "image", name: `${item.shot_ids[0] ?? "镜头"}首帧（重试）`, sourceNodeKey: "video_image_assets", hueSeed: 90 });
                item.status = "completed";
                item.asset_id = assetId;
                item.error_message = null;
              }
              current.content = content;
              node.validationResults = node.validationResults.filter((v) => v.rule_id !== "all_frames_ready");
              publishEvent({ event_type: "artifact.version_created", project_id: projectId, lesson_id: lessonId, node_key: nodeKey, task_id: null, payload: { artifact_version_id: current.artifact_version_id, item_id: itemId } });
            },
          });
          return ok({ task, artifact_version: null, node: node.summary }, { status: 202 });
        }
        return fail(422, "INVALID_ACTION", "该步骤不支持此操作。");
      }
      // 单页 / 单套修订
      case "revise": {
        const instruction = body.instruction?.trim();
        if (!instruction) {
          return fail(422, "VALIDATION_FAILED", "请填写修改意见。", { details: { field_errors: { instruction: "修改意见不能为空" } } });
        }
        const task = startTask({
          taskType: `item_revise:${nodeKey}`,
          projectId,
          lessonId,
          nodeKey,
          itemId,
          durationMs: 4200,
          estimatedCostMinor: 60,
          actualCostMinor: 55,
          providerName: "启明文本云",
          prevNodeStatus: node.summary.status,
          onComplete: () => {
            const content = structuredClone(node.artifactVersions[0].content) as Record<string, unknown>;
            if (nodeKey === "ppt_pages") {
              const pages = (content as unknown as PptPagesContent).pages;
              const page = pages.find((p) => p.page_id === itemId);
              if (page) {
                page.status = "needs_review";
                const textBlock = page.blocks.find((b) => b.type === "text" || b.type === "bullets");
                if (textBlock) textBlock.text = `${textBlock.text}（已按修改意见调整：${instruction}）`.trim();
                page.speaker_notes = `${page.speaker_notes}（修订：${instruction}）`;
              }
            } else if (nodeKey === "intro_design") {
              const intro = content as unknown as IntroDesignContent;
              for (const category of intro.categories) {
                for (const option of category.options) {
                  if (option.option_id === itemId) {
                    option.summary = `${option.summary}（已按修改意见调整：${instruction}）`;
                    option.status = "needs_review";
                  }
                }
              }
            }
            bumpVersion(content, "generated");
          },
        });
        return ok({ task, artifact_version: null, node: node.summary }, { status: 202 });
      }
      // 锁定创意重出锚点
      case "lock_creative_redo_anchor": {
        const task = startTask({
          taskType: "anchor_redo",
          projectId,
          lessonId,
          nodeKey,
          itemId,
          durationMs: 3600,
          estimatedCostMinor: 30,
          actualCostMinor: 28,
          providerName: "启明文本云",
          prevNodeStatus: node.summary.status,
          onComplete: () => {
            const content = structuredClone(node.artifactVersions[0].content) as Record<string, unknown>;
            const intro = content as unknown as IntroDesignContent;
            for (const category of intro.categories) {
              for (const option of category.options) {
                if (option.option_id === itemId) {
                  option.creative_locked = true;
                  option.status = "needs_review";
                  option.anchors = option.anchors.map((anchor) => ({ ...anchor, status: "confirmed", description: `${anchor.description}（锚点已重新生成）` }));
                }
              }
            }
            node.validationResults = node.validationResults.filter((v) => v.rule_id !== "anchors_confirmed");
            node.summary.status = "needs_review";
            bumpVersion(content, "generated");
          },
        });
        return ok({ task, artifact_version: null, node: node.summary }, { status: 202 });
      }
      // 更换页面配图（资产选择器一键带入）
      case "replace_image": {
        const assetId = String(body.payload?.asset_id ?? "");
        if (!assetId || !db.assets.has(assetId)) {
          return fail(422, "VALIDATION_FAILED", "请选择要使用的图片资产。", { details: { field_errors: { asset_id: "资产不存在" } } });
        }
        const content = structuredClone(latest.content) as Record<string, unknown>;
        if (nodeKey === "ppt_pages") {
          const pages = (content as unknown as PptPagesContent).pages;
          const page = pages.find((p) => p.page_id === itemId);
          if (!page) return fail(404, "NOT_FOUND", "页面不存在。");
          page.image_asset_ids = [assetId];
        } else if (nodeKey === "video_fine_storyboard") {
          const shots = (content as { shots?: Array<{ shot_id: string; first_frame_asset_id: string | null }> }).shots ?? [];
          const shot = shots.find((s) => s.shot_id === itemId);
          if (!shot) return fail(404, "NOT_FOUND", "镜头不存在。");
          shot.first_frame_asset_id = assetId;
        } else {
          return fail(422, "INVALID_ACTION", "该步骤不支持更换图片。");
        }
        const record = db.assets.get(assetId);
        if (record) {
          record.usage.push({ node_key: nodeKey, node_title: getNodeDef(nodeKey)?.title ?? nodeKey, lesson_id: lessonId, lesson_title: found.lessonState.lesson.title, artifact_version_id: latest.artifact_version_id, relation: nodeKey === "video_fine_storyboard" ? "first_frame" : "reference" });
          record.asset.usage_count = record.usage.length;
        }
        const artifact = bumpVersion(content, "edited");
        return ok({ task: null, artifact_version: artifact, node: node.summary });
      }
      // 复制为自定义方案
      case "duplicate_as_custom": {
        if (nodeKey !== "intro_design") return fail(422, "INVALID_ACTION", "该步骤不支持此操作。");
        const content = structuredClone(latest.content) as Record<string, unknown>;
        const intro = content as unknown as IntroDesignContent;
        for (const category of intro.categories) {
          const source = category.options.find((o) => o.option_id === itemId);
          if (source) {
            category.options.push({
              ...structuredClone(source),
              option_id: nextId(db, "opt_custom"),
              title: `${source.title}（自定义副本）`,
              status: "draft",
              creative_locked: false,
            });
          }
        }
        const artifact = bumpVersion(content, "edited");
        return ok({ task: null, artifact_version: artifact, node: node.summary });
      }
      default:
        return fail(422, "INVALID_ACTION", "不支持的列表项操作。");
    }
  }),
];
