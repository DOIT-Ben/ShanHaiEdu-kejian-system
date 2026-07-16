import { setActiveDb, type MockDb } from "./db";
import { applyPlatformSeed } from "./fixtures/platform";
import { seedProjects } from "./fixtures/projects";
import { resolveScenario, type ScenarioDefinition } from "./scenarios";
import { clearAllTimers, startTask, setNodeStatus } from "./engine";
import { publishEvent } from "./events";
import { makeArtifact } from "./fixtures/projects";
import { buildEvidenceContent } from "./fixtures/content";
import { generateNodeContent } from "./generation";

/** 初始化（或重置）Mock 数据库并启动场景内的进行中任务。 */
export function seedDb(scenarioId?: string | null, options?: { speedFactor?: number }): MockDb {
  clearAllTimers();
  const scenario: ScenarioDefinition = resolveScenario(scenarioId);
  const db: MockDb = {
    scenario: scenario.id,
    flags: scenario.flags,
    speedFactor: options?.speedFactor ?? 1,
    seq: 0,
    session: null,
    firstMeServed: false,
    divisionConflictServed: false,
    accounts: [],
    projects: new Map(),
    tasks: new Map(),
    taskCallbacks: new Map(),
    idempotency: new Map(),
    assets: new Map(),
    fileNames: new Map(),
    events: [],
    users: [],
    organizations: [],
    providers: [],
    models: [],
    routes: [],
    budgets: {
      currency: "CNY",
      platform_daily_minor_units: 0,
      teacher_quota_minor_units: 0,
      project_default_minor_units: 0,
      node_run_max_minor_units: 0,
      overage_policy: "pause",
      row_version: 1,
    },
    modelRuns: [],
    templates: new Map(),
    workflows: [],
    workflowDetails: new Map(),
    audit: [],
  };
  setActiveDb(db);
  applyPlatformSeed(db);
  seedProjects(db);
  startSeededTasks(db);
  if (db.flags.providerDegraded || db.flags.paidFallbackConfirm) {
    publishEvent({
      event_type: "provider.degraded",
      project_id: "proj_alpha",
      lesson_id: null,
      node_key: null,
      task_id: null,
      payload: { provider_id: "prov_video_1", provider_name: "潮汐视频云", reason: "上游服务连续超时，已自动降级" },
    });
  }
  return db;
}

/** 场景中的「进行中」任务：让页面打开时就能看到实时进度与完成流转。 */
function startSeededTasks(db: MockDb): void {
  const flags = db.flags;

  if (flags.textbookUploadRunning) {
    startTask({
      taskType: "textbook_parse",
      projectId: "proj_beta",
      durationMs: 16_000,
      failure: flags.parseFails ? { code: "PARSE_FAILED", message: "教材解析失败：第 12 页版面无法识别。未产生模型费用，可直接重试。", retryable: true } : null,
      onComplete: (mockDb) => {
        const beta = mockDb.projects.get("proj_beta");
        if (!beta) return;
        beta.evidence = makeArtifact({
          artifactType: "textbook_evidence",
          versionNumber: 1,
          status: "needs_review",
          content: buildEvidenceContent() as unknown as Record<string, unknown>,
          createdMinutesAgo: 0,
        });
        beta.project.textbook_status = "evidence_ready";
        publishEvent({ event_type: "artifact.version_created", project_id: "proj_beta", lesson_id: null, node_key: null, task_id: null, payload: { artifact_version_id: beta.evidence.artifact_version_id, artifact_type: "textbook_evidence" } });
      },
    });
  }

  if (flags.lessonPlanStreaming) {
    const project = db.projects.get("proj_alpha");
    const lessonState = project?.lessons.find((l) => l.lesson.lesson_id === "lesson_a3");
    if (project && lessonState) {
      const task = startTask({
        taskType: "node_run:lesson_plan",
        projectId: "proj_alpha",
        lessonId: "lesson_a3",
        nodeKey: "lesson_plan",
        durationMs: 20_000,
        estimatedCostMinor: 90,
        actualCostMinor: 86,
        providerName: "启明文本云",
        prevNodeStatus: "ready",
        onComplete: (mockDb) => {
          const proj = mockDb.projects.get("proj_alpha");
          const ls = proj?.lessons.find((l) => l.lesson.lesson_id === "lesson_a3");
          const node = ls?.nodes.get("lesson_plan");
          if (!proj || !ls || !node) return;
          const generated = generateNodeContent(mockDb, { project: proj, lessonState: ls, nodeKey: "lesson_plan", revisionInstruction: null });
          const artifact = makeArtifact({ artifactType: "lesson_plan", versionNumber: 1, status: "needs_review", content: generated.content, createdMinutesAgo: 0 });
          node.artifactVersions.unshift(artifact);
          node.validationResults = generated.validation ?? [];
          node.summary.status = "needs_review";
          node.activeTaskId = null;
          publishEvent({ event_type: "artifact.version_created", project_id: "proj_alpha", lesson_id: "lesson_a3", node_key: "lesson_plan", task_id: null, payload: { artifact_version_id: artifact.artifact_version_id, version_number: 1 } });
          publishEvent({ event_type: "node.status_changed", project_id: "proj_alpha", lesson_id: "lesson_a3", node_key: "lesson_plan", task_id: null, payload: { status: "needs_review" } });
        },
      });
      const node = lessonState.nodes.get("lesson_plan");
      if (node) node.activeTaskId = task.task_id;
    }
  }

  if (flags.pptExportRunning) {
    const project = db.projects.get("proj_alpha");
    const lessonState = project?.lessons.find((l) => l.lesson.lesson_id === "lesson_a1");
    const node = lessonState?.nodes.get("ppt_export");
    if (project && lessonState && node) {
      node.summary.status = "queued";
      node.summary.blocker_message = null;
      const task = startTask({
        taskType: "node_run:ppt_export",
        projectId: "proj_alpha",
        lessonId: "lesson_a1",
        nodeKey: "ppt_export",
        durationMs: 18_000,
        estimatedCostMinor: 0,
        providerName: "内置版式引擎",
        longPipeline: true,
        prevNodeStatus: "ready",
        onComplete: (mockDb) => {
          const proj = mockDb.projects.get("proj_alpha");
          const ls = proj?.lessons.find((l) => l.lesson.lesson_id === "lesson_a1");
          const exportNode = ls?.nodes.get("ppt_export");
          if (!proj || !ls || !exportNode) return;
          const generated = generateNodeContent(mockDb, { project: proj, lessonState: ls, nodeKey: "ppt_export", revisionInstruction: null });
          const artifact = makeArtifact({ artifactType: "ppt_export", versionNumber: 1, status: "needs_review", content: generated.content, createdMinutesAgo: 0 });
          exportNode.artifactVersions.unshift(artifact);
          exportNode.summary.status = "needs_review";
          exportNode.activeTaskId = null;
          publishEvent({ event_type: "artifact.version_created", project_id: "proj_alpha", lesson_id: "lesson_a1", node_key: "ppt_export", task_id: null, payload: { artifact_version_id: artifact.artifact_version_id, version_number: 1 } });
        },
      });
      node.activeTaskId = task.task_id;
    }
  }

  if (flags.videoFinalProcessing) {
    const project = db.projects.get("proj_alpha");
    const lessonState = project?.lessons.find((l) => l.lesson.lesson_id === "lesson_a1");
    const audioNode = lessonState?.nodes.get("video_audio_subtitle");
    if (project && lessonState && audioNode) {
      const audioTask = startTask({
        taskType: "node_run:video_audio_subtitle",
        projectId: "proj_alpha",
        lessonId: "lesson_a1",
        nodeKey: "video_audio_subtitle",
        durationMs: 14_000,
        estimatedCostMinor: 60,
        providerName: "知音语音",
        prevNodeStatus: "ready",
        onComplete: (mockDb) => {
          const proj = mockDb.projects.get("proj_alpha");
          const ls = proj?.lessons.find((l) => l.lesson.lesson_id === "lesson_a1");
          const node = ls?.nodes.get("video_audio_subtitle");
          if (!proj || !ls || !node) return;
          const generated = generateNodeContent(mockDb, { project: proj, lessonState: ls, nodeKey: "video_audio_subtitle", revisionInstruction: null });
          const artifact = makeArtifact({ artifactType: "video_audio_subtitle", versionNumber: 1, status: "needs_review", content: generated.content, createdMinutesAgo: 0 });
          node.artifactVersions.unshift(artifact);
          node.summary.status = "needs_review";
          node.activeTaskId = null;
          publishEvent({ event_type: "artifact.version_created", project_id: "proj_alpha", lesson_id: "lesson_a1", node_key: "video_audio_subtitle", task_id: null, payload: { artifact_version_id: artifact.artifact_version_id, version_number: 1 } });
          setNodeStatus(mockDb, "proj_alpha", "lesson_a1", "video_final_cut", "ready");
        },
      });
      audioNode.activeTaskId = audioTask.task_id;
    }
  }
}
