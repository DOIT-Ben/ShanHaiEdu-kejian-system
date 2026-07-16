import type {
  ArtifactVersion,
  Asset,
  Lesson,
  NodeSummary,
  Project,
  ValidationResult,
} from "@/shared/api/types";
import type { NodeStatus } from "@/shared/lib/status";
import { LESSON_NODES, getNodeDef, type WorkflowNodeDef } from "@/entities/workflow/nodes";
import { getDb, minutesAgo, nextId, type LessonState, type MockDb, type NodeState, type ProjectState } from "../db";
import { makeImageFileObject, makeFileObject } from "./files";
import { makePromptVersion } from "./prompts";
import {
  buildAudioSubtitleContent,
  buildClipsContent,
  buildDivisionContent,
  buildEvidenceContent,
  buildFinalCutContent,
  buildFineStoryboardContent,
  buildImageAssetsContent,
  buildIntroDesignContent,
  buildLessonPlanContent,
  buildMasterImageContent,
  buildMasterScriptContent,
  buildPptOutlineContent,
  buildPptPagesContent,
  buildRoughStoryboardContent,
  buildShotPromptsContent,
  buildVisualDirectionContent,
  ROUGH_SHOTS,
} from "./content";

/** 节点输入表单的轻量 schema（检查器「输入」页签渲染）。 */
function inputSchemaFor(nodeKey: string): Record<string, unknown> {
  const fieldsMap: Record<string, unknown[]> = {
    lesson_plan: [
      { key: "teaching_style", label: "教学风格", type: "select", options: ["探究式", "启发式", "讲授式"] },
      { key: "class_duration", label: "课时时长（分钟）", type: "number" },
      { key: "extra_requirements", label: "补充要求", type: "textarea", placeholder: "例如：增加小组合作环节" },
    ],
    intro_design: [
      { key: "tone", label: "整体基调", type: "select", options: ["温馨", "活泼", "奇幻"] },
      { key: "avoid_topics", label: "回避题材", type: "textarea", placeholder: "例如：避免食物浪费场景" },
    ],
    ppt_outline: [{ key: "page_budget", label: "目标页数", type: "number" }],
    ppt_pages: [{ key: "text_density", label: "文字密度", type: "select", options: ["精简", "适中", "详细"] }],
    ppt_assets: [{ key: "candidate_count", label: "每图候选数", type: "number" }],
    video_master_script: [{ key: "duration_target", label: "目标时长（秒）", type: "number" }],
    video_visual_direction: [{ key: "style_preference", label: "风格偏好", type: "textarea", placeholder: "例如：偏水彩质感" }],
    video_master_image: [{ key: "candidate_count", label: "候选数量", type: "number" }],
    video_rough_storyboard: [{ key: "max_shot_seconds", label: "单镜头最长（秒）", type: "number" }],
    video_image_assets: [{ key: "batch_note", label: "批量备注", type: "textarea" }],
    video_fine_storyboard: [{ key: "subtitle_max_chars", label: "字幕单行字数上限", type: "number" }],
    video_shot_prompts: [{ key: "extra_negative", label: "追加负向提示", type: "textarea" }],
    video_clips: [{ key: "per_shot_retry", label: "失败自动重试次数", type: "number" }],
    video_audio_subtitle: [{ key: "voice", label: "声线", type: "select", options: ["亲切童声（女）", "沉稳男声", "标准女声"] }],
    video_final_cut: [{ key: "with_watermark", label: "包含片尾标识", type: "switch" }],
    delivery: [],
  };
  return { fields: fieldsMap[nodeKey] ?? [] };
}

function defaultInputValues(nodeKey: string): Record<string, unknown> {
  const defaults: Record<string, Record<string, unknown>> = {
    lesson_plan: { teaching_style: "探究式", class_duration: 40, extra_requirements: "" },
    intro_design: { tone: "温馨", avoid_topics: "" },
    ppt_outline: { page_budget: 14 },
    ppt_pages: { text_density: "适中" },
    ppt_assets: { candidate_count: 2 },
    video_master_script: { duration_target: 90 },
    video_visual_direction: { style_preference: "" },
    video_master_image: { candidate_count: 3 },
    video_rough_storyboard: { max_shot_seconds: 20 },
    video_image_assets: { batch_note: "" },
    video_fine_storyboard: { subtitle_max_chars: 18 },
    video_shot_prompts: { extra_negative: "" },
    video_clips: { per_shot_retry: 1 },
    video_audio_subtitle: { voice: "亲切童声（女）" },
    video_final_cut: { with_watermark: true },
  };
  return defaults[nodeKey] ?? {};
}

export function makeArtifact(input: {
  artifactType: string;
  versionNumber: number;
  status: ArtifactVersion["status"];
  content: Record<string, unknown>;
  source?: "generated" | "edited" | "corrected";
  promptVersionId?: string | null;
  fileObjects?: ArtifactVersion["file_objects"];
  staleReason?: string | null;
  createdMinutesAgo?: number;
}): ArtifactVersion {
  const db = getDb();
  return {
    artifact_version_id: nextId(db, "av"),
    artifact_type: input.artifactType,
    version_number: input.versionNumber,
    status: input.status,
    content: input.content,
    row_version: 1,
    file_objects: input.fileObjects ?? [],
    source: input.source ?? "generated",
    model_run_id: input.source === "edited" ? null : nextId(db, "mr"),
    prompt_version_id: input.promptVersionId ?? null,
    stale_reason: input.staleReason ?? null,
    approved_at: input.status === "approved" ? minutesAgo((input.createdMinutesAgo ?? 120) - 10) : null,
    created_at: minutesAgo(input.createdMinutesAgo ?? 120),
  };
}

export function makeNodeState(
  def: WorkflowNodeDef,
  status: NodeStatus,
  options?: {
    artifacts?: ArtifactVersion[];
    promptCount?: number;
    validation?: ValidationResult[];
    blockerMessage?: string | null;
    progress?: number;
    selectedAssetIds?: string[];
  },
): NodeState {
  const artifacts = options?.artifacts ?? [];
  const prompts =
    def.capability && (options?.promptCount ?? (artifacts.length > 0 ? 1 : 0)) > 0
      ? Array.from({ length: options?.promptCount ?? 1 }, (_, i) =>
          makePromptVersion({ nodeKey: def.key, versionNumber: i + 1, createdMinutesAgo: 180 - i * 30 }),
        )
      : def.capability
        ? [makePromptVersion({ nodeKey: def.key, versionNumber: 1, createdMinutesAgo: 200 })]
        : [];
  const summary: NodeSummary = {
    node_key: def.key,
    title: def.title,
    group: def.group,
    status,
    progress_percent: options?.progress ?? (status === "approved" ? 100 : 0),
    blocker_message: options?.blockerMessage ?? null,
    capability: def.capability,
    skippable: def.skippable,
  };
  return {
    summary,
    description: def.description,
    inputSchema: inputSchemaFor(def.key),
    inputValues: defaultInputValues(def.key),
    inputRowVersion: 1,
    draftContent: null,
    draftRowVersion: 1,
    selectedAssetIds: options?.selectedAssetIds ?? [],
    promptVersions: prompts,
    artifactVersions: artifacts,
    validationResults: options?.validation ?? [],
    activeTaskId: null,
  };
}

function registerAsset(input: {
  projectId: string;
  lessonId: string | null;
  assetType: string;
  name: string;
  status: Asset["status"];
  sourceNodeKey: string;
  thumbnailLabel?: string;
  hueSeed?: number;
  fileName?: string;
  mimeType?: string;
  sizeBytes?: number;
  usage?: Array<{ nodeKey: string; relation: "input" | "reference" | "first_frame" | "master_image" | "clip_source" | "output" }>;
}): { assetId: string; fileObjectId: string } {
  const db = getDb();
  const assetId = nextId(db, "asset");
  const isImage = input.assetType === "image";
  const file = isImage
    ? makeImageFileObject(input.thumbnailLabel ?? input.name, input.hueSeed ?? 1, input.name)
    : makeFileObject({
        fileName: input.fileName ?? `${input.name}.bin`,
        mimeType: input.mimeType ?? "application/octet-stream",
        sizeBytes: input.sizeBytes ?? 1_000_000,
      });
  const asset: Asset = {
    asset_id: assetId,
    asset_type: input.assetType,
    name: input.name,
    status: input.status,
    current_version_id: `${assetId}_v1`,
    current_version_number: 1,
    thumbnail_url: isImage ? file.preview_url : null,
    source_node_key: input.sourceNodeKey,
    source_model_name: isImage ? "教学插画·标准" : input.assetType === "video" ? "教学视频·标准" : input.assetType === "audio" ? "旁白配音·标准" : null,
    lesson_id: input.lessonId,
    usage_count: input.usage?.length ?? 0,
    created_at: minutesAgo(300),
  };
  db.assets.set(assetId, {
    projectId: input.projectId,
    asset,
    versions: [
      {
        asset_version_id: `${assetId}_v1`,
        version_number: 1,
        status: input.status,
        file_object: file,
        source_model_name: asset.source_model_name,
        created_at: minutesAgo(300),
      },
    ],
    usage: (input.usage ?? []).map((u) => ({
      node_key: u.nodeKey,
      node_title: getNodeDef(u.nodeKey)?.title ?? u.nodeKey,
      lesson_id: input.lessonId,
      lesson_title: null,
      artifact_version_id: null,
      relation: u.relation,
    })),
  });
  return { assetId, fileObjectId: file.file_object_id };
}

function makeLesson(projectId: string, lessonId: string, seq: number, title: string, lessonType: string): Lesson {
  return {
    lesson_id: lessonId,
    project_id: projectId,
    lesson_key: `L${seq}`,
    sequence_number: seq,
    title,
    lesson_type: lessonType,
    content_boundary: { textbook_pages: seq === 1 ? "P89-91" : seq === 2 ? "P92-93" : "P93-94" },
    status: "active",
    stage_summary: {},
  };
}

/** 旗舰课时：lesson_a1（中游视频阶段，覆盖大多数演示场景）。 */
function buildLessonA1(db: MockDb, projectId: string): LessonState {
  const flags = db.flags;
  const lesson = makeLesson(projectId, "lesson_a1", 1, "认识几分之一", "new_knowledge");
  const nodes = new Map<string, NodeState>();

  // 教案：v1 被 v2 取代，v2 已批准（artifact.stale 场景中 v3 触发下游失效）
  const planV1 = makeArtifact({ artifactType: "lesson_plan", versionNumber: 1, status: "superseded", content: buildLessonPlanContent(lesson.title, 1) as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 30 });
  const planV2 = makeArtifact({ artifactType: "lesson_plan", versionNumber: 2, status: "approved", content: buildLessonPlanContent(lesson.title, 2) as unknown as Record<string, unknown>, source: "edited", createdMinutesAgo: 60 * 26 });
  const planArtifacts = [planV2, planV1];
  if (flags.staleDownstream) {
    const planV3 = makeArtifact({ artifactType: "lesson_plan", versionNumber: 3, status: "approved", content: buildLessonPlanContent(lesson.title, 2) as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 2 });
    planV2.status = "superseded";
    planArtifacts.unshift(planV3);
  }
  nodes.set("lesson_plan", makeNodeState(getNodeDef("lesson_plan")!, "approved", { artifacts: planArtifacts, promptCount: 2 }));

  // 导入设计：应用向方案1已批准并选定
  const introContent = buildIntroDesignContent({ approvedOptionId: "opt_application_1", selectedOptionId: "opt_application_1" });
  nodes.set(
    "intro_design",
    makeNodeState(getNodeDef("intro_design")!, "approved", {
      artifacts: [makeArtifact({ artifactType: "intro_design", versionNumber: 1, status: "approved", content: introContent as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 24 })],
    }),
  );

  // PPT 链
  const outlineStatus: NodeStatus = flags.staleDownstream ? "stale" : "approved";
  nodes.set(
    "ppt_outline",
    makeNodeState(getNodeDef("ppt_outline")!, outlineStatus, {
      artifacts: [
        makeArtifact({
          artifactType: "ppt_outline",
          versionNumber: 1,
          status: flags.staleDownstream ? "stale" : "approved",
          content: buildPptOutlineContent(lesson.title) as unknown as Record<string, unknown>,
          staleReason: flags.staleDownstream ? "上游「十二部分教案」已批准新版本 v3" : null,
          createdMinutesAgo: 60 * 22,
        }),
      ],
    }),
  );

  const pptIllu1 = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "image", name: "情境导入·分月饼插图", status: "approved", sourceNodeKey: "ppt_assets", thumbnailLabel: "分月饼", hueSeed: 3, usage: [{ nodeKey: "ppt_pages", relation: "output" }] });
  const pptIllu2 = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "image", name: "认识1/2·等分示意图", status: "approved", sourceNodeKey: "ppt_assets", thumbnailLabel: "1/2 示意", hueSeed: 7, usage: [{ nodeKey: "ppt_pages", relation: "output" }] });
  const pptIllu3 = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "image", name: "比较1/2与1/4插图", status: "needs_review", sourceNodeKey: "ppt_assets", thumbnailLabel: "比大小", hueSeed: 11, usage: [] });

  const pagesContent = buildPptPagesContent(lesson.title);
  pagesContent.pages[1].image_asset_ids = [pptIllu1.assetId];
  pagesContent.pages[3].image_asset_ids = [pptIllu2.assetId];
  pagesContent.pages[8].image_asset_ids = [pptIllu3.assetId];
  pagesContent.pages.forEach((p) => {
    if (p.page_no <= 10) p.status = "approved";
  });
  nodes.set(
    "ppt_pages",
    makeNodeState(getNodeDef("ppt_pages")!, "approved", {
      artifacts: [makeArtifact({ artifactType: "ppt_pages", versionNumber: 1, status: "approved", content: pagesContent as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 20 })],
    }),
  );
  nodes.set(
    "ppt_assets",
    makeNodeState(getNodeDef("ppt_assets")!, "approved", {
      artifacts: [
        makeArtifact({
          artifactType: "ppt_assets",
          versionNumber: 1,
          status: "approved",
          content: { generated_asset_ids: [pptIllu1.assetId, pptIllu2.assetId, pptIllu3.assetId] },
          createdMinutesAgo: 60 * 18,
        }),
      ],
      selectedAssetIds: [pptIllu1.assetId, pptIllu2.assetId],
    }),
  );
  // 关键样张待批准（ppt.key_sample_review）
  nodes.set(
    "ppt_preview",
    makeNodeState(getNodeDef("ppt_preview")!, "needs_review", {
      artifacts: [
        makeArtifact({
          artifactType: "ppt_preview",
          versionNumber: 1,
          status: "needs_review",
          content: { key_sample_page_ids: ["page_1", "page_4", "page_9"], note: "请确认封面、概念页与比较页三张关键样张的版式。" },
          createdMinutesAgo: 60 * 6,
        }),
      ],
      validation: [
        { rule_id: "body_pure_white", severity: "info", passed: true, message: "正文页均为纯白底" },
        { rule_id: "font_size_min", severity: "warning", passed: false, message: "第 12 页正文字号低于建议最小值 18pt", action: "调整该页文字密度或拆分页面" },
      ],
    }),
  );
  nodes.set("ppt_export", makeNodeState(getNodeDef("ppt_export")!, "locked", { blockerMessage: "等待整册预览确认后开始导出" }));

  // 视频链
  nodes.set(
    "video_master_script",
    makeNodeState(getNodeDef("video_master_script")!, flags.staleDownstream ? "stale" : "approved", {
      artifacts: [
        makeArtifact({
          artifactType: "video_master_script",
          versionNumber: 1,
          status: flags.staleDownstream ? "stale" : "approved",
          content: buildMasterScriptContent("分月饼") as unknown as Record<string, unknown>,
          staleReason: flags.staleDownstream ? "上游「十二部分教案」已批准新版本 v3" : null,
          createdMinutesAgo: 60 * 16,
        }),
      ],
    }),
  );
  nodes.set(
    "video_visual_direction",
    makeNodeState(getNodeDef("video_visual_direction")!, "approved", {
      artifacts: [makeArtifact({ artifactType: "video_visual_direction", versionNumber: 1, status: "approved", content: buildVisualDirectionContent() as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 15 })],
    }),
  );

  const master1 = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "image", name: "视觉母图候选A·庭院月夜", status: "approved", sourceNodeKey: "video_master_image", thumbnailLabel: "母图A", hueSeed: 21, usage: [{ nodeKey: "video_image_assets", relation: "master_image" }] });
  const master2 = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "image", name: "视觉母图候选B·餐桌特写", status: "rejected", sourceNodeKey: "video_master_image", thumbnailLabel: "母图B", hueSeed: 27, usage: [] });
  const master3 = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "image", name: "视觉母图候选C·星空构图", status: "rejected", sourceNodeKey: "video_master_image", thumbnailLabel: "母图C", hueSeed: 33, usage: [] });
  nodes.set(
    "video_master_image",
    makeNodeState(getNodeDef("video_master_image")!, "approved", {
      artifacts: [
        makeArtifact({
          artifactType: "video_master_image",
          versionNumber: 1,
          status: "approved",
          content: buildMasterImageContent(
            [
              { candidateId: "cand_1", assetId: master1.assetId, summary: "庭院月夜全景，暖橙+月夜蓝" },
              { candidateId: "cand_2", assetId: master2.assetId, summary: "餐桌特写构图" },
              { candidateId: "cand_3", assetId: master3.assetId, summary: "星空仰视构图" },
            ],
            master1.assetId,
          ) as unknown as Record<string, unknown>,
          createdMinutesAgo: 60 * 12,
        }),
      ],
      selectedAssetIds: [master1.assetId],
    }),
  );
  nodes.set(
    "video_rough_storyboard",
    makeNodeState(getNodeDef("video_rough_storyboard")!, "approved", {
      artifacts: [makeArtifact({ artifactType: "video_rough_storyboard", versionNumber: 1, status: "approved", content: buildRoughStoryboardContent() as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 10 })],
    }),
  );

  // 图片资产：镜头首帧（partial 场景下 shot_7 失败）
  const frameAssets: Record<string, string | null> = {};
  const imageItems = ROUGH_SHOTS.map((shot) => {
    const failed = flags.imagePartialFail && shot.shotNo === 7;
    if (failed) {
      frameAssets[`shot_${shot.shotNo}`] = null;
      return { imageId: `img_shot_${shot.shotNo}`, assetId: null, shotIds: [`shot_${shot.shotNo}`], summary: shot.description, failed: true };
    }
    const { assetId } = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "image", name: `镜头${shot.shotNo}首帧·${shot.sceneTitle}`, status: "approved", sourceNodeKey: "video_image_assets", thumbnailLabel: `镜头${shot.shotNo}`, hueSeed: 40 + shot.shotNo, usage: [{ nodeKey: "video_fine_storyboard", relation: "first_frame" }] });
    frameAssets[`shot_${shot.shotNo}`] = assetId;
    return { imageId: `img_shot_${shot.shotNo}`, assetId, shotIds: [`shot_${shot.shotNo}`], summary: shot.description };
  });
  nodes.set(
    "video_image_assets",
    makeNodeState(getNodeDef("video_image_assets")!, flags.imagePartialFail ? "needs_review" : "approved", {
      artifacts: [
        makeArtifact({
          artifactType: "video_image_assets",
          versionNumber: 1,
          status: flags.imagePartialFail ? "needs_review" : "approved",
          content: buildImageAssetsContent(imageItems) as unknown as Record<string, unknown>,
          createdMinutesAgo: 60 * 8,
        }),
      ],
      validation: flags.imagePartialFail
        ? [{ rule_id: "all_frames_ready", severity: "error", passed: false, message: "镜头 7 首帧生成失败，可单独重试", action: "重试失败镜头" }]
        : [],
    }),
  );

  // 细分镜 / 提示词 / 片段：按场景推进
  const clipStage = flags.clipApprovalReady || flags.videoFinalProcessing || flags.deliveryCompleted || flags.paidFallbackConfirm || flags.clipPartialFail;
  const fineStatus: NodeStatus = clipStage ? "approved" : "needs_review";
  nodes.set(
    "video_fine_storyboard",
    makeNodeState(getNodeDef("video_fine_storyboard")!, fineStatus, {
      artifacts: [makeArtifact({ artifactType: "video_fine_storyboard", versionNumber: 1, status: clipStage ? "approved" : "needs_review", content: buildFineStoryboardContent(frameAssets) as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 5 })],
    }),
  );
  nodes.set(
    "video_shot_prompts",
    makeNodeState(getNodeDef("video_shot_prompts")!, clipStage ? "approved" : "locked", {
      artifacts: clipStage
        ? [makeArtifact({ artifactType: "video_shot_prompts", versionNumber: 1, status: "approved", content: buildShotPromptsContent(frameAssets) as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 4 })]
        : [],
      blockerMessage: clipStage ? null : "等待细分镜批准",
    }),
  );

  if (clipStage) {
    interface SeedClip {
      clipId: string;
      shotId: string;
      shotNo: number;
      status: "queued" | "generating" | "completed" | "failed" | "approved";
      assetId?: string | null;
      duration?: number;
      attempt?: number;
      error?: string | null;
    }
    const clips: SeedClip[] = ROUGH_SHOTS.map((shot) => {
      const failed = flags.clipPartialFail && shot.shotNo === 4;
      if (failed) {
        return { clipId: `clip_${shot.shotNo}_1`, shotId: `shot_${shot.shotNo}`, shotNo: shot.shotNo, status: "failed" as const, error: flags.paidFallbackConfirm ? "潮汐视频云连续超时；可切换到备用服务「星河视频」重试（该镜头已产生费用 ¥15.00，切换后将再次计费，需确认）。" : "视频生成超时，可重试该镜头。", attempt: 1 };
      }
      const { assetId } = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "video", name: `镜头${shot.shotNo}片段`, status: flags.videoFinalProcessing || flags.deliveryCompleted ? "approved" : "needs_review", sourceNodeKey: "video_clips", fileName: `clip_shot_${shot.shotNo}.mp4`, mimeType: "video/mp4", sizeBytes: 6_000_000 + shot.shotNo * 120_000, usage: [{ nodeKey: "video_final_cut", relation: "clip_source" }] });
      const approvedClip = flags.videoFinalProcessing || flags.deliveryCompleted || (flags.clipApprovalReady && shot.shotNo !== 3);
      return { clipId: `clip_${shot.shotNo}_1`, shotId: `shot_${shot.shotNo}`, shotNo: shot.shotNo, status: (approvedClip ? "approved" : "completed") as "approved" | "completed", assetId, duration: shot.duration };
    });
    if (flags.clipApprovalReady) {
      // 镜头3有两个候选，等待批准其一
      const { assetId } = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "video", name: "镜头3片段·候选2", status: "needs_review", sourceNodeKey: "video_clips", fileName: "clip_shot_3_v2.mp4", mimeType: "video/mp4", sizeBytes: 6_400_000, usage: [] });
      clips.push({ clipId: "clip_3_2", shotId: "shot_3", shotNo: 3, status: "completed", assetId, duration: 10, attempt: 2 });
    }
    const clipsApproved = flags.videoFinalProcessing || flags.deliveryCompleted;
    nodes.set(
      "video_clips",
      makeNodeState(getNodeDef("video_clips")!, clipsApproved ? "approved" : "needs_review", {
        artifacts: [makeArtifact({ artifactType: "video_clips", versionNumber: 1, status: clipsApproved ? "approved" : "needs_review", content: buildClipsContent(clips) as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 3 })],
        validation: flags.clipPartialFail ? [{ rule_id: "all_clips_ready", severity: "error", passed: false, message: "镜头 4 片段生成失败（部分成功），其余镜头不受影响", action: "重试失败镜头" }] : [],
      }),
    );
  } else {
    nodes.set("video_clips", makeNodeState(getNodeDef("video_clips")!, "locked", { blockerMessage: "等待镜头提示词批准" }));
  }

  if (flags.videoFinalProcessing) {
    nodes.set("video_audio_subtitle", makeNodeState(getNodeDef("video_audio_subtitle")!, "running", { progress: 60 }));
    nodes.set("video_final_cut", makeNodeState(getNodeDef("video_final_cut")!, "queued", { blockerMessage: null }));
  } else if (flags.deliveryCompleted) {
    const audio = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "audio", name: "旁白配音轨", status: "approved", sourceNodeKey: "video_audio_subtitle", fileName: "narration.mp3", mimeType: "audio/mpeg", sizeBytes: 2_200_000, usage: [{ nodeKey: "video_final_cut", relation: "input" }] });
    const srt = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "subtitle", name: "字幕文件", status: "approved", sourceNodeKey: "video_audio_subtitle", fileName: "subtitles.srt", mimeType: "application/x-subrip", sizeBytes: 4_200, usage: [{ nodeKey: "video_final_cut", relation: "input" }] });
    nodes.set(
      "video_audio_subtitle",
      makeNodeState(getNodeDef("video_audio_subtitle")!, "approved", {
        artifacts: [makeArtifact({ artifactType: "video_audio_subtitle", versionNumber: 1, status: "approved", content: buildAudioSubtitleContent(audio.assetId, srt.assetId) as unknown as Record<string, unknown>, createdMinutesAgo: 100 })],
      }),
    );
    const finalVideo = registerAsset({ projectId, lessonId: lesson.lesson_id, assetType: "video", name: "导入视频成片", status: "approved", sourceNodeKey: "video_final_cut", fileName: "认识几分之一_导入视频.mp4", mimeType: "video/mp4", sizeBytes: 48_500_000, usage: [] });
    nodes.set(
      "video_final_cut",
      makeNodeState(getNodeDef("video_final_cut")!, "approved", {
        artifacts: [makeArtifact({ artifactType: "video_final_cut", versionNumber: 1, status: "approved", content: buildFinalCutContent(finalVideo.assetId) as unknown as Record<string, unknown>, createdMinutesAgo: 80 })],
      }),
    );
  } else {
    nodes.set("video_audio_subtitle", makeNodeState(getNodeDef("video_audio_subtitle")!, "locked", { blockerMessage: "等待全部镜头片段批准" }));
    nodes.set("video_final_cut", makeNodeState(getNodeDef("video_final_cut")!, "locked", { blockerMessage: "等待声音与字幕完成" }));
  }

  nodes.set("delivery", makeNodeState(getNodeDef("delivery")!, flags.deliveryCompleted ? "approved" : "ready"));

  return { lesson, nodes, currentNodeKey: flags.clipApprovalReady || flags.clipPartialFail ? "video_clips" : "video_fine_storyboard" };
}

/** 编写阶段课时：lesson_a2（教案待审核、九套导入待审）。 */
function buildLessonA2(db: MockDb, projectId: string): LessonState {
  const flags = db.flags;
  const lesson = makeLesson(projectId, "lesson_a2", 2, "认识几分之几", "new_knowledge");
  const nodes = new Map<string, NodeState>();

  const planV1 = makeArtifact({ artifactType: "lesson_plan", versionNumber: 1, status: "superseded", content: buildLessonPlanContent(lesson.title, 1) as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 9 });
  const planV2 = makeArtifact({ artifactType: "lesson_plan", versionNumber: 2, status: "needs_review", content: buildLessonPlanContent(lesson.title, 2) as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 2 });
  nodes.set(
    "lesson_plan",
    makeNodeState(getNodeDef("lesson_plan")!, "needs_review", {
      artifacts: [planV2, planV1],
      promptCount: 2,
      validation: [
        { rule_id: "sections_complete", severity: "error", passed: true, message: "十二部分结构完整" },
        { rule_id: "duration_sum", severity: "warning", passed: false, message: "教学过程各环节时长合计 42 分钟，超过课时 40 分钟", action: "调整环节时长或在批准时说明理由" },
        { rule_id: "objectives_measurable", severity: "info", passed: true, message: "教学目标包含可观察行为动词" },
      ],
    }),
  );

  nodes.set(
    "intro_design",
    makeNodeState(getNodeDef("intro_design")!, flags.anchorFailed ? "revision_required" : "needs_review", {
      artifacts: [
        makeArtifact({
          artifactType: "intro_design",
          versionNumber: 1,
          status: flags.anchorFailed ? "needs_review" : "needs_review",
          content: buildIntroDesignContent({ anchorFailed: flags.anchorFailed }) as unknown as Record<string, unknown>,
          createdMinutesAgo: 60 * 3,
        }),
      ],
      validation: flags.anchorFailed
        ? [{ rule_id: "anchors_confirmed", severity: "error", passed: false, message: "故事向方案的课程锚点未通过校验：创意可保留，需重新生成锚点", action: "锁定创意重出锚点" }]
        : [],
    }),
  );

  for (const key of ["ppt_outline", "ppt_pages", "ppt_assets", "ppt_preview", "ppt_export"]) {
    nodes.set(key, makeNodeState(getNodeDef(key)!, "locked", { blockerMessage: "等待教案批准" }));
  }
  nodes.set("video_master_script", makeNodeState(getNodeDef("video_master_script")!, "locked", { blockerMessage: "等待教案与导入设计批准" }));
  for (const key of ["video_visual_direction", "video_master_image", "video_rough_storyboard", "video_image_assets", "video_fine_storyboard", "video_shot_prompts", "video_clips", "video_audio_subtitle", "video_final_cut"]) {
    nodes.set(key, makeNodeState(getNodeDef(key)!, "locked", { blockerMessage: "等待上一步完成" }));
  }
  nodes.set("delivery", makeNodeState(getNodeDef("delivery")!, "locked", { blockerMessage: "等待教案批准" }));

  return { lesson, nodes, currentNodeKey: "lesson_plan" };
}

/** 新开课时：lesson_a3（全新，可开始；streaming 场景下教案生成中）。 */
function buildLessonA3(db: MockDb, projectId: string): LessonState {
  const flags = db.flags;
  const lesson = makeLesson(projectId, "lesson_a3", 3, "分数的简单计算与练习", "practice");
  const nodes = new Map<string, NodeState>();

  nodes.set(
    "lesson_plan",
    makeNodeState(getNodeDef("lesson_plan")!, flags.lessonPlanStreaming ? "running" : "ready", {
      progress: flags.lessonPlanStreaming ? 45 : 0,
    }),
  );
  nodes.set("intro_design", makeNodeState(getNodeDef("intro_design")!, "ready"));
  for (const node of LESSON_NODES) {
    if (nodes.has(node.key)) continue;
    nodes.set(node.key, makeNodeState(node, "locked", { blockerMessage: "等待上游步骤完成" }));
  }
  return { lesson, nodes, currentNodeKey: "lesson_plan" };
}

/** 全新课时状态（课时划分批准后创建课时用）。 */
export function makeFreshLessonState(
  projectId: string,
  lessonId: string,
  seq: number,
  title: string,
  lessonType: string,
): LessonState {
  const lesson = makeLesson(projectId, lessonId, seq, title, lessonType);
  const nodes = new Map<string, NodeState>();
  nodes.set("lesson_plan", makeNodeState(getNodeDef("lesson_plan")!, "ready"));
  nodes.set("intro_design", makeNodeState(getNodeDef("intro_design")!, "ready"));
  for (const node of LESSON_NODES) {
    if (!nodes.has(node.key)) {
      nodes.set(node.key, makeNodeState(node, "locked", { blockerMessage: "等待上游步骤完成" }));
    }
  }
  return { lesson, nodes, currentNodeKey: "lesson_plan" };
}

function makeProject(input: {
  projectId: string;
  name: string;
  grade: number;
  status: Project["status"];
  textbookStatus: Project["textbook_status"];
  divisionStatus: Project["division_status"];
  lessonCount: number;
  progress: number;
  spentMinor: number;
  updatedMinutesAgo: number;
  outputScope?: { ppt: boolean; video: boolean };
}): Project {
  return {
    project_id: input.projectId,
    name: input.name,
    subject: "primary_math",
    grade: input.grade,
    textbook_version: "人教版",
    volume: input.grade === 3 ? "三年级上册" : input.grade === 2 ? "二年级下册" : "三年级下册",
    status: input.status,
    execution_mode: "semi_auto",
    progress_percent: input.progress,
    textbook_status: input.textbookStatus,
    division_status: input.divisionStatus,
    lesson_count: input.lessonCount,
    budget_minor_units: 30_000,
    spent_minor_units: input.spentMinor,
    currency: "CNY",
    output_scope: input.outputScope ?? { ppt: true, video: true },
    row_version: 3,
    created_at: minutesAgo(60 * 24 * 7),
    updated_at: minutesAgo(input.updatedMinutesAgo),
  };
}

export function seedProjects(db: MockDb): void {
  const flags = db.flags;
  if (flags.emptyProjects) return;

  // ---------- 项目 Alpha：分数的初步认识（旗舰演示） ----------
  const alphaId = "proj_alpha";
  const alphaLessons = [buildLessonA1(db, alphaId), buildLessonA2(db, alphaId), buildLessonA3(db, alphaId)];
  const alphaEvidence = makeArtifact({
    artifactType: "textbook_evidence",
    versionNumber: 1,
    status: "approved",
    content: buildEvidenceContent() as unknown as Record<string, unknown>,
    createdMinutesAgo: 60 * 24 * 3,
  });
  const alphaDivisionV1 = makeArtifact({ artifactType: "lesson_division", versionNumber: 1, status: "superseded", content: buildDivisionContent() as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 24 * 2 - 60 });
  const alphaDivision = makeArtifact({ artifactType: "lesson_division", versionNumber: 2, status: "approved", content: buildDivisionContent() as unknown as Record<string, unknown>, source: "edited", createdMinutesAgo: 60 * 24 * 2 });
  const alpha: ProjectState = {
    project: makeProject({
      projectId: alphaId,
      name: "三年级上·分数的初步认识",
      grade: 3,
      status: "active",
      textbookStatus: "evidence_ready",
      divisionStatus: "approved",
      lessonCount: 3,
      progress: flags.deliveryCompleted ? 100 : 62,
      spentMinor: flags.budgetAuthRequired ? 28_400 : 9_860,
      updatedMinutesAgo: 30,
    }),
    evidence: alphaEvidence,
    division: alphaDivision,
    divisionVersions: [alphaDivision, alphaDivisionV1],
    lessons: alphaLessons,
    delivery: { status: "not_ready", items: [], blockers: [], package_task_id: null, packaged_at: null, package_file: null },
  };
  db.projects.set(alphaId, alpha);

  // ---------- 项目 Beta：表内除法（教材/课时划分阶段） ----------
  const betaId = "proj_beta";
  const betaParseFailed = Boolean(flags.parseFails);
  const betaUploading = Boolean(flags.textbookUploadRunning);
  const betaEvidence =
    betaParseFailed || betaUploading
      ? null
      : makeArtifact({
          artifactType: "textbook_evidence",
          versionNumber: 1,
          status: flags.evidencePartial ? "needs_review" : "approved",
          content: buildEvidenceContent({ partial: flags.evidencePartial }) as unknown as Record<string, unknown>,
          createdMinutesAgo: 60 * 20,
        });
  const betaDivision =
    betaEvidence && !flags.evidencePartial
      ? makeArtifact({ artifactType: "lesson_division", versionNumber: 1, status: "needs_review", content: buildDivisionContent() as unknown as Record<string, unknown>, createdMinutesAgo: 60 * 4 })
      : null;
  const beta: ProjectState = {
    project: makeProject({
      projectId: betaId,
      name: "二年级下·表内除法",
      grade: 2,
      status: "active",
      textbookStatus: betaUploading ? "parsing" : betaParseFailed ? "parse_failed" : "evidence_ready",
      divisionStatus: betaDivision ? "needs_review" : "none",
      lessonCount: 0,
      progress: 12,
      spentMinor: 320,
      updatedMinutesAgo: betaUploading ? 2 : 60 * 4,
    }),
    evidence: betaEvidence,
    division: betaDivision,
    divisionVersions: betaDivision ? [betaDivision] : [],
    lessons: [],
    delivery: { status: "not_ready", items: [], blockers: [], package_task_id: null, packaged_at: null, package_file: null },
  };
  db.projects.set(betaId, beta);

  // ---------- 项目 Gamma：草稿 ----------
  const gammaId = "proj_gamma";
  db.projects.set(gammaId, {
    project: makeProject({ projectId: gammaId, name: "三年级下·小数的初步认识（筹备）", grade: 3, status: "draft", textbookStatus: "none", divisionStatus: "none", lessonCount: 0, progress: 0, spentMinor: 0, updatedMinutesAgo: 60 * 24 * 2 }),
    evidence: null,
    division: null,
    divisionVersions: [],
    lessons: [],
    delivery: { status: "not_ready", items: [], blockers: [], package_task_id: null, packaged_at: null, package_file: null },
  });

  // ---------- 项目 Delta：已归档 ----------
  const deltaId = "proj_delta";
  db.projects.set(deltaId, {
    project: { ...makeProject({ projectId: deltaId, name: "二年级上·位置与方向（已归档）", grade: 2, status: "archived", textbookStatus: "evidence_ready", divisionStatus: "approved", lessonCount: 2, progress: 100, spentMinor: 15_200, updatedMinutesAgo: 60 * 24 * 30 }) },
    evidence: null,
    division: null,
    divisionVersions: [],
    lessons: [],
    delivery: { status: "completed", items: [], blockers: [], package_task_id: null, packaged_at: minutesAgo(60 * 24 * 30), package_file: null },
  });
}
