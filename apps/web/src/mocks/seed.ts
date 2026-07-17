import { db, resetDb, type MockLesson, type MockNodeRun, type MockBranch } from "./db";
import { ID, uuid } from "./ids";
import {
  briefPlanDefinition,
  buildIntroOptionSet,
  buildPptPages,
  buildShots,
  lessonPlanContent,
  lessonPlanDefinition,
  lessonPlanWarning,
  promptFixtures,
} from "./fixtures";
import { STEPS } from "@/entities/workflow/steps";

/**
 * 种子世界：
 * proj_alpha「认识几分之几」= 主演示项目（lessonA2 处于教案待确认，PPT/视频链路推进中）。
 * proj_empty = 教材未上传的空项目。
 * proj_auto = 全自动项目（预算暂停场景）。
 * 场景（scenarios.ts）在本基线上做增量调整。
 */

const T0 = "2026-07-15T01:00:00Z";
const T1 = "2026-07-16T02:00:00Z";
const T2 = "2026-07-16T08:30:00Z";

function svg(label: string, tone = "#315ef5"): string {
  const text = encodeURIComponent(label);
  return `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><rect width="640" height="360" fill="${encodeURIComponent(
    tone,
  )}" opacity="0.12"/><rect x="8" y="8" width="624" height="344" fill="none" stroke="${encodeURIComponent(
    tone,
  )}" stroke-width="2" rx="16"/><text x="320" y="190" font-size="28" text-anchor="middle" fill="${encodeURIComponent(
    tone,
  )}" font-family="sans-serif">${text}</text></svg>`;
}

export function nodeTitle(nodeKey: string): string {
  const map: Record<string, string> = {
    lesson_plan: "教案",
    intro_options: "三类九套导入设计",
    intro_selection: "导入方案选择",
    ppt_outline: "PPT 大纲",
    ppt_cover: "PPT 封面",
    ppt_body: "PPT 正文",
    ppt_export: "PPT 导出",
    video_script: "母版剧本",
    video_storyboard: "粗分镜",
    video_style: "画面风格",
    video_assets: "镜头图片",
    video_clips: "视频片段",
    video_compose: "视频合成",
  };
  return map[nodeKey] ?? nodeKey;
}

function branch(state: MockBranch["state"], summary: string | null = null, next: string | null = null): MockBranch {
  return { state, summary, next_step_key: next };
}

function seedUsers(): void {
  db.users = [
    { id: ID.userTeacher, name: "林晓雨", email: "teacher@shanhai.edu", password: "demo1234", roles: ["teacher"] },
    { id: ID.userContentAdmin, name: "赵敏芝", email: "content@shanhai.edu", password: "demo1234", roles: ["content_admin"] },
    { id: ID.userModelAdmin, name: "王建国", email: "model@shanhai.edu", password: "demo1234", roles: ["model_admin"] },
    { id: ID.userSystemAdmin, name: "陈系统", email: "admin@shanhai.edu", password: "demo1234", roles: ["system_admin", "content_admin", "model_admin"] },
  ];
}

function seedProjects(): void {
  db.projects.set(ID.projAlpha, {
    id: ID.projAlpha,
    title: "认识几分之几",
    knowledge_point: "认识几分之几",
    grade: "三年级上册",
    textbook_edition: "人教版",
    status: "active",
    automation_mode: "assisted",
    created_at: T0,
    updated_at: T2,
    etag: 3,
  });
  db.projects.set(ID.projEmpty, {
    id: ID.projEmpty,
    title: "面积单位换算",
    knowledge_point: "面积单位换算",
    grade: "三年级下册",
    textbook_edition: "人教版",
    status: "draft",
    automation_mode: "manual",
    created_at: T1,
    updated_at: T1,
    etag: 1,
  });
  db.projects.set(ID.projAuto, {
    id: ID.projAuto,
    title: "小数的初步认识",
    knowledge_point: "小数的初步认识",
    grade: "三年级下册",
    textbook_edition: "人教版",
    status: "active",
    automation_mode: "automatic",
    created_at: T1,
    updated_at: T2,
    etag: 2,
  });

  db.materials.set(ID.projAlpha, {
    id: ID.materialAlpha,
    project_id: ID.projAlpha,
    status: "scope_confirmed",
    file_name: "人教版三上-认识几分之几.pdf",
    page_count: 6,
    knowledge_scope: "教材第 90–93 页：认识几分之几、简单分数读写。",
    evidence: [
      { page_no: 90, summary: "折纸涂色情境引入四分之三", excerpt: "把一张正方形纸平均分成 4 份……" },
      { page_no: 91, summary: "几分之几的读写与含义" },
      { page_no: 92, summary: "练习：用分数表示涂色部分" },
      { page_no: 93, summary: "拓展：生活中的分数" },
    ],
    failure_reason: null,
    uploaded_at: T0,
  });

  db.divisions.set(ID.projAlpha, {
    project_id: ID.projAlpha,
    status: "approved",
    source_evidence_note: "依据教材 90–93 页划分为 3 课时。",
    entries: [
      { entry_id: uuid(1101), position: 1, title: "认识几分之一", focus: "初步认识几分之一，会折会说", duration_minutes: 40, lesson_id: ID.lessonA1 },
      { entry_id: uuid(1102), position: 2, title: "认识几分之几", focus: "理解几分之几的含义，会读写简单分数", duration_minutes: 40, lesson_id: ID.lessonA2 },
      { entry_id: uuid(1103), position: 3, title: "分数的简单应用", focus: "用分数解决简单实际问题", duration_minutes: 40, lesson_id: ID.lessonA3 },
    ],
    etag: 4,
  });

  db.automations.set(ID.projAlpha, {
    project_id: ID.projAlpha,
    state: "idle",
    paused_reason: null,
    paused_detail: null,
    pending_estimate: null,
    spent_minor_units: 9860,
    budget_minor_units: 30000,
  });
  db.automations.set(ID.projAuto, {
    project_id: ID.projAuto,
    state: "paused",
    paused_reason: "budget_confirmation_required",
    paused_detail: "接下来将为 12 张镜头图片调用图像模型，预计费用超过单次授权额度。",
    pending_estimate: { minor_units: 5600, currency: "CNY", summary: "12 张镜头图片 × 图像生成" },
    spent_minor_units: 21400,
    budget_minor_units: 30000,
  });

  db.deliveries.set(ID.projAlpha, { project_id: ID.projAlpha, status: "not_ready", package: null });
  db.deliveries.set(ID.projAuto, { project_id: ID.projAuto, status: "not_ready", package: null });
}

function seedLessons(): void {
  const lessons: MockLesson[] = [
    {
      id: ID.lessonA1,
      project_id: ID.projAlpha,
      position: 1,
      title: "认识几分之一",
      focus: "初步认识几分之一，会折会说",
      duration_minutes: 40,
      branches: {
        lesson_plan: branch("approved", "教案 v3 已批准"),
        intro_options: branch("approved", "已选「披萨店的失踪一角」"),
        ppt: branch("approved", "PPTX v2 已导出"),
        video: branch("disabled", "本课时未启用视频"),
      },
      updated_at: T1,
      etag: 2,
    },
    {
      id: ID.lessonA2,
      project_id: ID.projAlpha,
      position: 2,
      title: "认识几分之几",
      focus: "理解几分之几的含义，会读写简单分数",
      duration_minutes: 40,
      branches: {
        lesson_plan: branch("review_required", "教案 v2 等待你确认", "lesson-plan-confirm"),
        intro_options: branch("review_required", "九套方案等待挑选", "intro-options"),
        ppt: branch("in_progress", "封面待选择", "ppt-cover"),
        video: branch("in_progress", "镜头片段制作中", "video-clips"),
      },
      updated_at: T2,
      etag: 5,
    },
    {
      id: ID.lessonA3,
      project_id: ID.projAlpha,
      position: 3,
      title: "分数的简单应用",
      focus: "用分数解决简单实际问题",
      duration_minutes: 40,
      branches: {
        lesson_plan: branch("not_ready", "等待生成"),
        intro_options: branch("not_ready", null),
        ppt: branch("disabled", "尚未启用"),
        video: branch("disabled", "尚未启用"),
      },
      updated_at: T1,
      etag: 1,
    },
  ];
  for (const lesson of lessons) db.lessons.set(lesson.id, lesson);
}

function seedNodeRuns(): void {
  const defs: [string, string, string, string | null, boolean][] = [
    // [nodeRunId, nodeKey, status, currentArtifactVersionId, skippable]
    [ID.nrLessonPlanA2, "lesson_plan", "review_required", ID.avLessonPlanA2, false],
    [ID.nrIntroOptionsA2, "intro_options", "review_required", ID.avIntroOptionsA2, true],
    [ID.nrIntroSelectionA2, "intro_selection", "ready", null, true],
    [ID.nrPptOutlineA2, "ppt_outline", "approved", ID.avPptOutlineA2, false],
    [ID.nrPptCoverA2, "ppt_cover", "review_required", null, false],
    [ID.nrPptBodyA2, "ppt_body", "not_ready", null, false],
    [ID.nrPptExportA2, "ppt_export", "not_ready", null, false],
    [ID.nrVideoScriptA2, "video_script", "approved", ID.avVideoScriptA2, false],
    [ID.nrVideoStoryboardA2, "video_storyboard", "approved", ID.avVideoStoryboardA2, false],
    [ID.nrVideoStyleA2, "video_style", "approved", null, false],
    [ID.nrVideoAssetsA2, "video_assets", "approved", null, false],
    [ID.nrVideoClipsA2, "video_clips", "partially_completed", null, false],
    [ID.nrVideoComposeA2, "video_compose", "not_ready", null, false],
  ];
  for (const [id, nodeKey, status, artifactId, skippable] of defs) {
    const run: MockNodeRun = {
      id,
      lesson_id: ID.lessonA2,
      project_id: ID.projAlpha,
      node_key: nodeKey,
      title: nodeTitle(nodeKey),
      status,
      current_artifact_version_id: artifactId,
      active_job_id: null,
      skippable,
      stale_reason: null,
      updated_at: T2,
    };
    db.nodeRuns.set(id, run);
  }

  // 提示词（每个生成节点都必须可见可编辑）
  for (const run of db.nodeRuns.values()) {
    const fixture = promptFixtures[run.node_key];
    if (!fixture) continue;
    db.prompts.set(run.id, {
      node_run_id: run.id,
      editable_prompt: fixture.editable,
      default_prompt: fixture.editable,
      prompt_revision_id: null,
      locked_layers: fixture.locked,
      context_summary: fixture.context,
      etag: 1,
    });
  }
}

function seedArtifacts(): void {
  db.artifactVersions.set(ID.avLessonPlanA2, {
    id: ID.avLessonPlanA2,
    node_run_id: ID.nrLessonPlanA2,
    kind: "lesson_plan",
    review_status: "review_required",
    version_no: 2,
    is_current: true,
    content: {
      definition: lessonPlanDefinition,
      data: lessonPlanContent,
    },
    content_definition_version_id: uuid(1201),
    validation_issues: [lessonPlanWarning],
    source: "generated",
    created_at: T2,
    approved_at: null,
    approval_note: null,
    etag: 2,
  });
  // v1 历史版本
  db.artifactVersions.set(uuid(4011), {
    id: uuid(4011),
    node_run_id: ID.nrLessonPlanA2,
    kind: "lesson_plan",
    review_status: "superseded",
    version_no: 1,
    is_current: false,
    content: { definition: lessonPlanDefinition, data: { ...lessonPlanContent, design_intent: "（初版）" } },
    content_definition_version_id: uuid(1201),
    validation_issues: [],
    source: "generated",
    created_at: T1,
    approved_at: null,
    approval_note: null,
    etag: 1,
  });

  db.artifactVersions.set(ID.avIntroOptionsA2, {
    id: ID.avIntroOptionsA2,
    node_run_id: ID.nrIntroOptionsA2,
    kind: "intro_option_set",
    review_status: "review_required",
    version_no: 1,
    is_current: true,
    content: {},
    content_definition_version_id: null,
    validation_issues: [],
    source: "generated",
    created_at: T1,
    approved_at: null,
    approval_note: null,
    etag: 1,
  });

  db.artifactVersions.set(ID.avPptOutlineA2, {
    id: ID.avPptOutlineA2,
    node_run_id: ID.nrPptOutlineA2,
    kind: "ppt_outline",
    review_status: "approved",
    version_no: 1,
    is_current: true,
    content: {
      pages: buildPptPages().map((p) => ({
        page_key: p.page_key,
        position: p.position,
        page_type: p.page_type,
        teaching_task: p.teaching_task,
        source_refs: p.source_refs,
      })),
    },
    content_definition_version_id: null,
    validation_issues: [],
    source: "generated",
    created_at: T1,
    approved_at: T1,
    approval_note: null,
    etag: 1,
  });

  db.artifactVersions.set(ID.avVideoScriptA2, {
    id: ID.avVideoScriptA2,
    node_run_id: ID.nrVideoScriptA2,
    kind: "video_master_script",
    review_status: "approved",
    version_no: 1,
    is_current: true,
    content: {
      master_script_id: uuid(1301),
      title: "巧克力守卫战",
      selected_option_key: "INTRO-STO-01",
      target_duration_seconds: 35,
      story_text:
        "夜晚，松鼠守卫把最珍贵的巧克力平均掰成四块藏进树洞木盒。清晨开盒，四块只剩一块，地上留着可疑爪印。松鼠警长挂出案情板立案侦查，要记录被偷走的巧克力到底有多少——粉笔停在「失窃：」后的空白处，问号闪烁。",
      scenes: [
        { scene_id: "SCENE-01", purpose: "建立宝物与平均分", visible_change: "整块巧克力变为四块入盒", narration: "松鼠守卫把最珍贵的巧克力平均分成了四块，藏进树洞。", sound_intent: "夜晚虫鸣" },
        { scene_id: "SCENE-02", purpose: "制造失窃悬念", visible_change: "四块只剩一块", narration: "第二天清晨，盒子里只剩下一块！", sound_intent: "悬疑渐入" },
        { scene_id: "SCENE-03", purpose: "立案并停在提问", visible_change: "案情板问号定格", narration: "被偷走的巧克力，到底占整块的多少？", sound_intent: "留白" },
      ],
      classroom_first_question: "被偷走的巧克力占整块的几分之几？",
      handoff_moment: "松鼠警长在案情板写下「失窃：？」的问号定格。",
      must_not_preteach: ["分数的读写", "分子分母含义"],
    },
    content_definition_version_id: null,
    validation_issues: [],
    source: "generated",
    created_at: T1,
    approved_at: T1,
    approval_note: null,
    etag: 1,
  });

  db.artifactVersions.set(ID.avVideoStoryboardA2, {
    id: ID.avVideoStoryboardA2,
    node_run_id: ID.nrVideoStoryboardA2,
    kind: "video_storyboard",
    review_status: "approved",
    version_no: 1,
    is_current: true,
    content: {
      beats: [
        { beat_key: "BEAT-01", scene_id: "SCENE-01", position: 1, event: "藏宝：平均分四块入盒", start_state: "完整巧克力", end_state: "四块入盒", estimated_seconds: 10, asset_needs: ["松鼠守卫", "树洞夜景", "四格巧克力"] },
        { beat_key: "BEAT-02", scene_id: "SCENE-02", position: 2, event: "失窃：只剩一块与爪印", start_state: "盒盖关闭", end_state: "惊讶与爪印", estimated_seconds: 10, asset_needs: ["松鼠守卫", "四格巧克力"] },
        { beat_key: "BEAT-03", scene_id: "SCENE-03", position: 3, event: "立案：问号定格", start_state: "案情板就绪", end_state: "粉笔停在空白", estimated_seconds: 15, asset_needs: ["松鼠守卫", "案情板"] },
      ],
    },
    content_definition_version_id: null,
    validation_issues: [],
    source: "generated",
    created_at: T1,
    approved_at: T1,
    approval_note: null,
    etag: 1,
  });
}

function seedIntro(): void {
  db.introOptionSets.set(ID.lessonA2, {
    lesson_id: ID.lessonA2,
    set: buildIntroOptionSet(ID.lessonA2),
    etag: 1,
  });
  // lessonA1 已完成选择（供项目总览展示）
  const setA1 = buildIntroOptionSet(ID.lessonA1);
  setA1.status = "approved";
  db.introOptionSets.set(ID.lessonA1, { lesson_id: ID.lessonA1, set: setA1, etag: 2 });
  db.introSelections.set(ID.lessonA1, {
    selection_id: uuid(1451),
    lesson_id: ID.lessonA1,
    option_set_version_id: setA1.option_set_id,
    option_key: "INTRO-SCI-01",
    choice_mode: "teacher_selected",
    selected_at: T1,
  });
}

function seedPpt(): void {
  const pages = buildPptPages();
  const ids = [ID.pageCoverA2, ID.pageBody1A2, ID.pageBody2A2, ID.pageBody3A2, uuid(605), uuid(606)];
  pages.forEach((spec, index) => {
    const pageId = ids[index];
    db.pptPages.set(pageId, {
      page_id: pageId,
      lesson_id: ID.lessonA2,
      spec,
      status: spec.page_type === "cover" ? "review_required" : "draft",
      preview_url: spec.page_type === "cover" ? null : svg(`${spec.page_key} 预览`),
      is_stale: false,
      stale_reason: null,
      asset_slots: spec.visual.asset_requirements.map((req) => ({
        slot_key: req.target_slot_key,
        status: spec.page_type === "cover" ? "pending" : "empty",
        asset_version_id: null,
        preview_url: null,
      })),
      etag: 1,
    });
  });

  // 封面候选（node_run=ppt_cover 的候选结果）
  const coverCandidates = [
    ["cover", "四分之三披萨 · 暖光留白", "#315ef5"],
    ["cover", "折纸彩格 · 山海蓝点缀", "#2449d8"],
    ["cover", "巧克力四格 · 俯拍构图", "#b56a09"],
  ] as const;
  coverCandidates.forEach(([itemKey, label, tone], index) => {
    const id = uuid(1701 + index);
    db.results.set(id, {
      id,
      batch_id: null,
      node_run_id: ID.nrPptCoverA2,
      item_key: itemKey,
      media_type: "image",
      review_state: "pending",
      technical_check: "passed",
      technical_check_detail: null,
      preview_url: svg(label, tone),
      duration_seconds: null,
      width: 1280,
      height: 720,
      saved_binding_id: null,
      created_at: T2,
    });
  });
}

function seedVideo(): void {
  const introSet = db.introOptionSets.get(ID.lessonA2)!.set;
  const selected = introSet.options.find((o) => o.option_key === "INTRO-STO-01")!;
  db.introSelections.set(ID.lessonA2, {
    selection_id: uuid(1452),
    lesson_id: ID.lessonA2,
    option_set_version_id: introSet.option_set_id,
    option_key: selected.option_key,
    choice_mode: "teacher_selected",
    selected_at: T1,
  });

  db.videoProjects.set(ID.videoProjectA2, {
    id: ID.videoProjectA2,
    lesson_id: ID.lessonA2,
    status: "active",
    intro_snapshot: {
      option_key: selected.option_key,
      title: selected.title,
      category: selected.category,
      independent_concept: selected.independent_concept,
      hook: selected.hook,
      viewer_value: selected.viewer_value,
      course_anchor: selected.course_anchor,
      classroom_first_question: selected.classroom_first_question,
      handoff_moment: selected.handoff_moment,
      must_not_preteach: selected.must_not_preteach,
      suggested_medium: selected.suggested_medium,
      duration_seconds: selected.duration_seconds,
    },
    style_contract: {
      id: uuid(1501),
      summary: "手工毛毡质感 · 暖色月光 · 圆润造型 · 低饱和夜景",
      rules: {
        medium: "毛毡定格动画质感",
        lighting: "暖色月光与台灯",
        palette: ["#2c4a7c", "#e8b04b", "#8b5a2b"],
        forbidden: ["文字", "水印", "恐怖元素", "写实血腥"],
      },
      master_image_url: svg("视觉母图 · 毛毡夜色", "#2449d8"),
    },
    target_duration_seconds: 35,
    created_at: T1,
  });

  const shots = buildShots();
  const shotIds = [ID.shotA2_1, ID.shotA2_2, ID.shotA2_3];
  const shotStates: ["adopted" | "failed" | "review_required", string | null][] = [
    ["adopted", null],
    ["failed", "模型服务返回画面缺陷：主体消失超过 2 秒。可直接重试该镜头。"],
    ["review_required", null],
  ];
  shots.forEach((shot, index) => {
    const id = shotIds[index];
    const [status, failureReason] = shotStates[index];
    db.shots.set(id, {
      id,
      video_project_id: ID.videoProjectA2,
      shot_key: shot.shot_id,
      position: shot.position,
      status,
      shot,
      current_clip:
        status === "adopted"
          ? {
              clip_id: uuid(1801),
              result_id: uuid(1811),
              preview_url: svg("镜头1 · 已采用片段", "#16855b"),
              saved_at: T2,
            }
          : null,
      active_job_id: null,
      failure_reason: failureReason,
      etag: 1,
    });
  });

  // 镜头1 的已保存候选 + 镜头3 的两个待挑选候选
  db.results.set(uuid(1811), {
    id: uuid(1811),
    batch_id: null,
    node_run_id: ID.nrVideoClipsA2,
    item_key: "SHOT-01",
    media_type: "video",
    review_state: "adopted",
    technical_check: "passed",
    technical_check_detail: null,
    preview_url: svg("镜头1 候选A", "#16855b"),
    duration_seconds: 10,
    width: 1280,
    height: 720,
    saved_binding_id: uuid(1801),
    created_at: T2,
  });
  [0, 1].forEach((i) => {
    const id = uuid(1821 + i);
    db.results.set(id, {
      id,
      batch_id: null,
      node_run_id: ID.nrVideoClipsA2,
      item_key: "SHOT-03",
      media_type: "video",
      review_state: "pending",
      technical_check: i === 0 ? "passed" : "failed",
      technical_check_detail: i === 0 ? null : "时长偏差超过容差（14.2s / 15s）。",
      preview_url: svg(`镜头3 候选${i === 0 ? "A" : "B"}`, i === 0 ? "#315ef5" : "#c73543"),
      duration_seconds: 15,
      width: 1280,
      height: 720,
      saved_binding_id: null,
      created_at: T2,
    });
  });
}

function seedCreation(): void {
  db.packages.set(ID.packageVideoAssetsA2, {
    package_id: ID.packageVideoAssetsA2,
    package_type: "image",
    status: "ready",
    source: {
      project_id: ID.projAlpha,
      lesson_unit_id: ID.lessonA2,
      node_run_id: ID.nrVideoAssetsA2,
      is_stale: false,
    },
    style_contract: {
      summary: "手工毛毡质感 · 暖色月光（继承视频画面风格）",
      forbidden: ["文字", "水印"],
    },
    items: [
      { item_key: "ASSET-CHAR-01", position: 1, title: "松鼠守卫（角色）", prompt: { description: "毛毡质感松鼠守卫立绘，胸前小挎包，圆润造型，正面与侧面参考", style: "毛毡定格动画", aspect_ratio: "1:1" }, output_spec: { media_type: "image", count: 2 }, target_slot_key: "video.asset.character.squirrel", consistency_key: "felt-night" },
      { item_key: "ASSET-SCENE-01", position: 2, title: "树洞夜景（场景）", prompt: { description: "月光下的大树与树洞空镜，无人物，毛毡质感", style: "毛毡定格动画", aspect_ratio: "16:9" }, output_spec: { media_type: "image", count: 2 }, target_slot_key: "video.asset.scene.treehole", consistency_key: "felt-night" },
      { item_key: "ASSET-PROP-01", position: 3, title: "四格巧克力（道具）", prompt: { description: "可平均掰成四块的巧克力单体，白色背景，毛毡质感", style: "毛毡定格动画", aspect_ratio: "1:1" }, output_spec: { media_type: "image", count: 2 }, target_slot_key: "video.asset.prop.chocolate", consistency_key: "felt-night" },
      { item_key: "ASSET-PROP-02", position: 4, title: "案情板（道具）", prompt: { description: "侦探案情板单体，贴着照片与线绳，无可读文字，毛毡质感", style: "毛毡定格动画", aspect_ratio: "3:4" }, output_spec: { media_type: "image", count: 2 }, target_slot_key: "video.asset.prop.caseboard", consistency_key: "felt-night" },
    ],
    target_rules: { default_project_id: ID.projAlpha, replace_mode: "reject_if_occupied" },
    created_at: T1,
  });

  db.batches.set(ID.batchFromPackage, {
    id: ID.batchFromPackage,
    studio_type: "image",
    title: "认识几分之几 · 镜头图片",
    status: "partially_completed",
    creation_package_id: ID.packageVideoAssetsA2,
    source_project_id: ID.projAlpha,
    source_project_title: "认识几分之几",
    default_save_target: "video.asset",
    style_contract: { summary: "手工毛毡质感 · 暖色月光" },
    items: [
      { id: uuid(2101), item_key: "ASSET-CHAR-01", position: 1, title: "松鼠守卫（角色）", status: "saved", prompt: { description: "毛毡质感松鼠守卫立绘，胸前小挎包，圆润造型", style: "毛毡定格动画", aspect_ratio: "1:1" }, output_spec: { media_type: "image", count: 2 }, reference_assets: [], target_slot_key: "video.asset.character.squirrel", consistency_key: "felt-night", adopted_result_id: uuid(2201), saved_binding_id: uuid(2301) },
      { id: uuid(2102), item_key: "ASSET-SCENE-01", position: 2, title: "树洞夜景（场景）", status: "review_required", prompt: { description: "月光下的大树与树洞空镜，无人物", style: "毛毡定格动画", aspect_ratio: "16:9" }, output_spec: { media_type: "image", count: 2 }, reference_assets: [], target_slot_key: "video.asset.scene.treehole", consistency_key: "felt-night", adopted_result_id: null, saved_binding_id: null },
      { id: uuid(2103), item_key: "ASSET-PROP-01", position: 3, title: "四格巧克力（道具）", status: "failed", prompt: { description: "可平均掰成四块的巧克力单体，白色背景", style: "毛毡定格动画", aspect_ratio: "1:1" }, output_spec: { media_type: "image", count: 2 }, reference_assets: [], target_slot_key: "video.asset.prop.chocolate", consistency_key: "felt-night", adopted_result_id: null, saved_binding_id: null },
      { id: uuid(2104), item_key: "ASSET-PROP-02", position: 4, title: "案情板（道具）", status: "ready", prompt: { description: "侦探案情板单体，贴着照片与线绳，无可读文字", style: "毛毡定格动画", aspect_ratio: "3:4" }, output_spec: { media_type: "image", count: 2 }, reference_assets: [], target_slot_key: "video.asset.prop.caseboard", consistency_key: "felt-night", adopted_result_id: null, saved_binding_id: null },
    ],
    active_job_id: null,
    created_at: T1,
    updated_at: T2,
    etag: 3,
  });

  // 批次候选
  const batchResults: [string, string, "adopted" | "pending", string][] = [
    [uuid(2201), "ASSET-CHAR-01", "adopted", "松鼠守卫 候选A"],
    [uuid(2202), "ASSET-CHAR-01", "pending", "松鼠守卫 候选B"],
    [uuid(2203), "ASSET-SCENE-01", "pending", "树洞夜景 候选A"],
    [uuid(2204), "ASSET-SCENE-01", "pending", "树洞夜景 候选B"],
  ];
  for (const [id, itemKey, state, label] of batchResults) {
    db.results.set(id, {
      id,
      batch_id: ID.batchFromPackage,
      node_run_id: null,
      item_key: itemKey,
      media_type: "image",
      review_state: state,
      technical_check: "passed",
      technical_check_detail: null,
      preview_url: svg(label),
      duration_seconds: null,
      width: 1024,
      height: 1024,
      saved_binding_id: state === "adopted" ? uuid(2301) : null,
      created_at: T2,
    });
  }

  db.batches.set(ID.batchIndependent, {
    id: ID.batchIndependent,
    studio_type: "image",
    title: "分数墙教学挂图",
    status: "draft",
    creation_package_id: null,
    source_project_id: null,
    source_project_title: null,
    default_save_target: null,
    style_contract: null,
    items: [
      { id: uuid(2111), item_key: "ITEM-01", position: 1, title: "分数墙教学挂图", status: "draft", prompt: { description: "分数墙教学挂图：1、1/2、1/3、1/4 分层排列，清新配色，适合三年级教室", style: "扁平插画", aspect_ratio: "3:4", count: 4 }, output_spec: { media_type: "image", count: 4 }, reference_assets: [], target_slot_key: null, consistency_key: null, adopted_result_id: null, saved_binding_id: null },
    ],
    active_job_id: null,
    created_at: T2,
    updated_at: T2,
    etag: 1,
  });
}

function seedAssets(): void {
  const entries: [string, string, "image" | "video_clip" | "document" | "ppt_page", string, string | null, string | null][] = [
    [uuid(2401), "松鼠守卫（角色）", "image", "视频 · 镜头图片", ID.lessonA2, "video.asset.character.squirrel"],
    [uuid(2402), "视觉母图 · 毛毡夜色", "image", "视频 · 画面风格", ID.lessonA2, "video.style.master"],
    [uuid(2403), "镜头1 · 已采用片段", "video_clip", "视频 · 正式片段", ID.lessonA2, "video.clip.SHOT-01"],
    [uuid(2404), "认识几分之一 · 教案", "document", "教案 · 已批准", ID.lessonA1, "lesson_plan.docx"],
    [uuid(2405), "认识几分之一 · PPTX", "ppt_page", "PPT · 已导出", ID.lessonA1, "ppt.pptx"],
  ];
  entries.forEach(([id, title, kind, usage, lessonId, slot]) => {
    db.assets.set(id, {
      id,
      project_id: ID.projAlpha,
      kind,
      title,
      usage_label: usage,
      source_label: "生成后保存",
      lesson_id: lessonId,
      lesson_title: lessonId ? db.lessons.get(lessonId)?.title ?? null : null,
      slot_key: slot,
      is_current: true,
      preview_url: svg(title),
      version_no: 1,
      created_at: T2,
    });
  });
}

function seedAdmin(): void {
  const providers: [string, string, ("text" | "image" | "video" | "tts" | "layout")[], "configured" | "missing" | "expiring", string | null][] = [
    [ID.providerText, "启明文本云", ["text"], "configured", "Kx3f"],
    [ID.providerImage, "绘山图像", ["image"], "configured", "9Bd2"],
    [ID.providerVideo, "潮汐视频云", ["video"], "configured", "7Hq1"],
    [ID.providerVideoBackup, "星河视频（备用）", ["video"], "configured", "2Mz8"],
    [ID.providerTts, "知音语音", ["tts"], "expiring", "5Pw4"],
    [ID.providerLayout, "内置版式引擎", ["layout"], "configured", null],
  ];
  providers.forEach(([id, name, capabilities, secretStatus, tail]) => {
    db.providers.set(id, {
      id,
      display_name: name,
      capabilities,
      base_url: name === "内置版式引擎" ? null : "https://gateway.internal/provider",
      enabled: true,
      secret_status: secretStatus,
      secret_tail: tail,
      last_test: { status: "passed", tested_at: T1, detail: null },
      updated_at: T1,
      etag: 1,
    });
  });

  db.contentPackages.set(ID.contentPkgLessonPlan, {
    id: ID.contentPkgLessonPlan,
    title: "小学数学教案结构（默认十二部分）",
    domain: "lesson_plan",
    status: "published",
    current_version_no: 3,
    definition_key: lessonPlanDefinition.definition_key,
    definition: lessonPlanDefinition,
    validation_issues: [],
    versions: [
      { version_no: 3, published_at: T1, note: "细化分层作业结构" },
      { version_no: 2, published_at: T0, note: "增加设计意图字段" },
      { version_no: 1, published_at: "2026-07-10T02:00:00Z", note: null },
    ],
    test_cases: [
      { key: "tc-structure", title: "结构完整性", status: "passed" },
      { key: "tc-render", title: "教师端渲染预览", status: "passed" },
      { key: "tc-export", title: "DOCX 导出映射", status: "passed" },
    ],
    usage: [{ project_title: "认识几分之几", version_no: 3 }],
    updated_at: T1,
  });
  db.contentPackages.set(ID.contentPkgIntroRules, {
    id: ID.contentPkgIntroRules,
    title: "三类九套独立创意与锚定规则",
    domain: "intro_options",
    status: "published",
    current_version_no: 2,
    definition_key: null,
    definition: null,
    validation_issues: [],
    versions: [
      { version_no: 2, published_at: T1, note: "强化交接时刻校验" },
      { version_no: 1, published_at: T0, note: null },
    ],
    test_cases: [
      { key: "tc-isolation", title: "独立创意隔离", status: "passed" },
      { key: "tc-unique-top", title: "最高推荐分唯一", status: "passed" },
    ],
    usage: [{ project_title: "认识几分之几", version_no: 2 }],
    updated_at: T1,
  });
  db.contentPackages.set(ID.contentPkgPptManual, {
    id: ID.contentPkgPptManual,
    title: "简案结构（五部分 · 试运行）",
    domain: "lesson_plan",
    status: "dry_run",
    current_version_no: 0,
    definition_key: briefPlanDefinition.definition_key,
    definition: briefPlanDefinition,
    validation_issues: [
      { key: "cp-timeline-widget", severity: "warning", message: "timeline 字段未指定 ui_widget，将使用默认时间线渲染器。" },
    ],
    versions: [],
    test_cases: [
      { key: "tc-structure", title: "结构完整性", status: "passed" },
      { key: "tc-render", title: "教师端渲染预览", status: "pending" },
    ],
    usage: [],
    updated_at: T2,
  });

  db.auditEvents = [
    { id: uuid(2501), actor_name: "林晓雨", action: "artifact.approve", resource_label: "认识几分之一 · 教案 v3", detail: null, occurred_at: T1 },
    { id: uuid(2502), actor_name: "林晓雨", action: "prompt.edit", resource_label: "认识几分之几 · 教案生成指令", detail: "修改后另存为新版本", occurred_at: T1 },
    { id: uuid(2503), actor_name: "赵敏芝", action: "content_package.publish", resource_label: "教案结构 v3", detail: null, occurred_at: T1 },
    { id: uuid(2504), actor_name: "王建国", action: "provider.update", resource_label: "知音语音", detail: "更新密钥（尾号 5Pw4）", occurred_at: T1 },
    { id: uuid(2505), actor_name: "林晓雨", action: "save_to_project.execute", resource_label: "镜头1 片段 → 认识几分之几", detail: null, occurred_at: T2 },
    { id: uuid(2506), actor_name: "陈系统", action: "user.role_change", resource_label: "赵敏芝 → content_admin", detail: null, occurred_at: T0 },
  ];
}

/** 构建默认世界；scenario handlers 在其上做增量修改。 */
export function seedDb(): void {
  resetDb();
  seedUsers();
  seedProjects();
  seedLessons();
  seedNodeRuns();
  seedArtifacts();
  seedIntro();
  seedPpt();
  seedVideo();
  seedCreation();
  seedAssets();
  seedAdmin();
}

export { svg as placeholderSvg };

/** 供工作台使用：lessonA2 之外的课时按需懒建节点。 */
export function ensureLessonNodeRuns(lessonId: string): void {
  const lesson = db.lessons.get(lessonId);
  if (!lesson) return;
  const existing = [...db.nodeRuns.values()].some((run) => run.lesson_id === lessonId);
  if (existing) return;
  const nodeKeys = [...new Set(STEPS.filter((s) => s.nodeKey).map((s) => s.nodeKey!))];
  nodeKeys.forEach((nodeKey, index) => {
    const id = `${lessonId.slice(0, 8)}-node-4000-8000-${String(index + 1).padStart(12, "0")}`;
    const isPlan = nodeKey === "lesson_plan";
    const branchOf = (): string => {
      if (nodeKey.startsWith("ppt")) return lesson.branches.ppt.state;
      if (nodeKey.startsWith("video")) return lesson.branches.video.state;
      if (nodeKey.startsWith("intro")) return lesson.branches.intro_options.state;
      return lesson.branches.lesson_plan.state;
    };
    const branchState = branchOf();
    const status = branchState === "disabled" ? "disabled" : isPlan ? "ready" : "not_ready";
    db.nodeRuns.set(id, {
      id,
      lesson_id: lessonId,
      project_id: lesson.project_id,
      node_key: nodeKey,
      title: nodeTitle(nodeKey),
      status,
      current_artifact_version_id: null,
      active_job_id: null,
      skippable: nodeKey.startsWith("intro"),
      stale_reason: null,
      updated_at: lesson.updated_at,
    });
    const fixture = promptFixtures[nodeKey];
    if (fixture) {
      db.prompts.set(id, {
        node_run_id: id,
        editable_prompt: fixture.editable,
        default_prompt: fixture.editable,
        prompt_revision_id: null,
        locked_layers: fixture.locked,
        context_summary: fixture.context,
        etag: 1,
      });
    }
  });
}
