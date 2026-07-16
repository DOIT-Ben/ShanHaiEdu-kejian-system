import type { ArtifactVersion, Task } from "@/shared/api/types";
import type { NodeStatus } from "@/shared/lib/status";
import { directDownstreamKeys, getNodeDef } from "@/entities/workflow/nodes";
import { getDb, nextId, nowIso, type LessonState, type MockDb, type NodeState, type ProjectState } from "./db";
import { publishEvent } from "./events";
import { makeArtifact } from "./fixtures/projects";
import { registerGeneratedAsset, generateNodeContent } from "./generation";

/** 能力对应的基准任务时长（毫秒）。 */
const CAPABILITY_DURATION: Record<string, number> = {
  text_generation: 4200,
  image_generation: 6000,
  video_generation: 9000,
  tts: 5000,
  pptx_render: 6000,
  video_compose: 8000,
};

export interface TaskSpec {
  taskType: string;
  projectId: string;
  lessonId?: string | null;
  nodeKey?: string | null;
  itemId?: string | null;
  durationMs?: number;
  estimatedCostMinor?: number;
  actualCostMinor?: number;
  providerName?: string | null;
  /** waiting_provider / downloading 阶段（长任务演示）。 */
  longPipeline?: boolean;
  failure?: { code: string; message: string; retryable: boolean; action?: string | null } | null;
  prevNodeStatus?: NodeStatus;
  onComplete?: (db: MockDb) => void;
}

const taskSpecs = new Map<string, TaskSpec>();
const taskTimers = new Map<string, ReturnType<typeof setTimeout>[]>();

function addTimer(taskId: string, timer: ReturnType<typeof setTimeout>): void {
  const list = taskTimers.get(taskId) ?? [];
  list.push(timer);
  taskTimers.set(taskId, list);
}

export function clearAllTimers(): void {
  for (const timers of taskTimers.values()) {
    for (const timer of timers) clearTimeout(timer);
  }
  taskTimers.clear();
  taskSpecs.clear();
}

function findNodeState(db: MockDb, projectId: string, lessonId: string | null | undefined, nodeKey: string | null | undefined): { project: ProjectState; lessonState: LessonState | null; node: NodeState | null } | null {
  const project = db.projects.get(projectId);
  if (!project) return null;
  if (!lessonId || !nodeKey) return { project, lessonState: null, node: null };
  const lessonState = project.lessons.find((l) => l.lesson.lesson_id === lessonId) ?? null;
  const node = lessonState?.nodes.get(nodeKey) ?? null;
  return { project, lessonState, node };
}

export function setNodeStatus(db: MockDb, projectId: string, lessonId: string, nodeKey: string, status: NodeStatus, progress?: number): void {
  const found = findNodeState(db, projectId, lessonId, nodeKey);
  if (!found?.node) return;
  found.node.summary.status = status;
  if (progress !== undefined) found.node.summary.progress_percent = progress;
  publishEvent({ event_type: "node.status_changed", project_id: projectId, lesson_id: lessonId, node_key: nodeKey, task_id: null, payload: { status } });
}

function emitTask(_db: MockDb, task: Task, eventType: string): void {
  publishEvent({
    event_type: eventType,
    project_id: task.project_id ?? "",
    lesson_id: task.lesson_id ?? null,
    node_key: task.node_key ?? null,
    task_id: task.task_id,
    payload: { status: task.status, progress_percent: task.progress_percent },
  });
}

export function startTask(spec: TaskSpec): Task {
  const db = getDb();
  const taskId = nextId(db, "task");
  const duration = Math.max(400, Math.round((spec.durationMs ?? 4000) * db.speedFactor));
  const task: Task = {
    task_id: taskId,
    task_type: spec.taskType,
    status: "queued",
    progress_percent: 0,
    progress_message: "任务已进入队列",
    retryable: false,
    cancellable: true,
    project_id: spec.projectId,
    lesson_id: spec.lessonId ?? null,
    node_key: spec.nodeKey ?? null,
    item_id: spec.itemId ?? null,
    provider_name: spec.providerName ?? null,
    estimated_cost_minor_units: spec.estimatedCostMinor ?? 0,
    actual_cost_minor_units: 0,
    cost_incurred: false,
    error: null,
    created_at: nowIso(),
    finished_at: null,
  };
  db.tasks.set(taskId, task);
  taskSpecs.set(taskId, spec);
  emitTask(db, task, "task.queued");
  if (spec.lessonId && spec.nodeKey) {
    setNodeStatus(db, spec.projectId, spec.lessonId, spec.nodeKey, "queued", 0);
  }

  const startDelay = Math.max(150, Math.round(500 * db.speedFactor));
  addTimer(taskId, setTimeout(() => {
    const current = db.tasks.get(taskId);
    if (!current || current.status !== "queued") return;
    current.status = "running";
    current.progress_message = "正在生成";
    emitTask(db, current, "task.started");
    if (spec.lessonId && spec.nodeKey) {
      setNodeStatus(db, spec.projectId, spec.lessonId, spec.nodeKey, "running", 5);
    }

    const steps = 5;
    for (let i = 1; i <= steps; i += 1) {
      addTimer(taskId, setTimeout(() => {
        const running = db.tasks.get(taskId);
        if (!running) return;
        if (running.status !== "running" && running.status !== "waiting_provider" && running.status !== "downloading") return;
        const percent = Math.min(95, Math.round((i / (steps + 1)) * 100));
        running.progress_percent = percent;
        if (spec.longPipeline) {
          if (i === 2) {
            running.status = "waiting_provider";
            running.progress_message = "等待模型服务返回";
          } else if (i === 4) {
            running.status = "downloading";
            running.progress_message = "下载生成产物";
          }
        } else {
          running.progress_message = `正在生成（${percent}%）`;
        }
        emitTask(db, running, "task.progress");
        if (spec.lessonId && spec.nodeKey) {
          const found = findNodeState(db, spec.projectId, spec.lessonId, spec.nodeKey);
          if (found?.node) found.node.summary.progress_percent = percent;
        }
      }, (duration / (steps + 1)) * i));
    }

    addTimer(taskId, setTimeout(() => {
      const finishing = db.tasks.get(taskId);
      if (!finishing) return;
      if (finishing.status === "cancel_requested" || finishing.status === "cancelled") return;
      if (spec.failure) {
        finishing.status = "failed";
        finishing.progress_message = "任务失败";
        finishing.retryable = spec.failure.retryable;
        finishing.cancellable = false;
        finishing.finished_at = nowIso();
        finishing.error = {
          code: spec.failure.code,
          message: spec.failure.message,
          retryable: spec.failure.retryable,
          action: spec.failure.action ?? null,
          details: {},
          trace_id: nextId(db, "trace"),
        };
        emitTask(db, finishing, "task.failed");
        if (spec.lessonId && spec.nodeKey) {
          setNodeStatus(db, spec.projectId, spec.lessonId, spec.nodeKey, "failed");
        }
        return;
      }
      finishing.status = "completed";
      finishing.progress_percent = 100;
      finishing.progress_message = "已完成";
      finishing.cancellable = false;
      finishing.finished_at = nowIso();
      const actual = spec.actualCostMinor ?? spec.estimatedCostMinor ?? 0;
      finishing.actual_cost_minor_units = actual;
      finishing.cost_incurred = actual > 0;
      if (actual > 0) {
        const project = db.projects.get(spec.projectId);
        if (project) {
          project.project.spent_minor_units = (project.project.spent_minor_units ?? 0) + actual;
          db.budgets.platform_daily_spent_minor_units = (db.budgets.platform_daily_spent_minor_units ?? 0) + actual;
          publishEvent({ event_type: "budget.updated", project_id: spec.projectId, lesson_id: null, node_key: null, task_id: taskId, payload: { spent_minor_units: project.project.spent_minor_units } });
        }
      }
      spec.onComplete?.(db);
      emitTask(db, finishing, "task.completed");
    }, duration));
  }, startDelay));

  return task;
}

export function cancelTask(taskId: string): Task | null {
  const db = getDb();
  const task = db.tasks.get(taskId);
  if (!task) return null;
  if (task.status !== "queued" && task.status !== "running" && task.status !== "waiting_provider" && task.status !== "downloading") {
    return task;
  }
  task.status = "cancel_requested";
  task.progress_message = "正在取消（已发出的模型调用可能仍会计费）";
  emitTask(db, task, "task.progress");
  const spec = taskSpecs.get(taskId);
  addTimer(taskId, setTimeout(() => {
    const current = db.tasks.get(taskId);
    if (!current || current.status !== "cancel_requested") return;
    current.status = "cancelled";
    current.cancellable = false;
    current.finished_at = nowIso();
    current.progress_message = "已取消";
    emitTask(db, current, "task.cancelled");
    if (spec?.lessonId && spec.nodeKey) {
      setNodeStatus(db, spec.projectId, spec.lessonId, spec.nodeKey, spec.prevNodeStatus ?? "ready");
    }
  }, Math.max(200, Math.round(800 * db.speedFactor))));
  return task;
}

export function retryTask(taskId: string): Task | null {
  const db = getDb();
  const failed = db.tasks.get(taskId);
  const spec = taskSpecs.get(taskId);
  if (!failed || !spec) return null;
  if (failed.status !== "failed" && failed.status !== "cancelled") return failed;
  return startTask({ ...spec, failure: null });
}

/**
 * 批准产物版本：同类旧版本置为 superseded，节点置为 approved，
 * 解锁下游；若下游已有产物则标记 stale。
 */
export function approveArtifact(db: MockDb, versionId: string, note?: string): ArtifactVersion | null {
  void note;
  for (const project of db.projects.values()) {
    // 项目级：教材证据 / 课时划分
    if (project.evidence?.artifact_version_id === versionId) {
      project.evidence.status = "approved";
      project.evidence.approved_at = nowIso();
      project.project.textbook_status = "evidence_ready";
      publishEvent({ event_type: "artifact.approved", project_id: project.project.project_id, lesson_id: null, node_key: null, task_id: null, payload: { artifact_version_id: versionId } });
      return project.evidence;
    }
    for (const lessonState of project.lessons) {
      for (const node of lessonState.nodes.values()) {
        const target = node.artifactVersions.find((v) => v.artifact_version_id === versionId);
        if (!target) continue;
        for (const version of node.artifactVersions) {
          if (version.artifact_version_id !== versionId && version.status === "approved") {
            version.status = "superseded";
          }
        }
        const hadApprovedBefore = node.artifactVersions.some(
          (v) => v.artifact_version_id !== versionId && v.status === "superseded",
        );
        target.status = "approved";
        target.approved_at = nowIso();
        node.summary.status = "approved";
        node.summary.progress_percent = 100;
        publishEvent({ event_type: "artifact.approved", project_id: project.project.project_id, lesson_id: lessonState.lesson.lesson_id, node_key: node.summary.node_key, task_id: null, payload: { artifact_version_id: versionId } });
        publishEvent({ event_type: "node.status_changed", project_id: project.project.project_id, lesson_id: lessonState.lesson.lesson_id, node_key: node.summary.node_key, task_id: null, payload: { status: "approved" } });
        refreshDownstream(db, project, lessonState, node.summary.node_key, hadApprovedBefore && target.version_number > 1);
        return target;
      }
    }
  }
  return null;
}

/** 上游批准后：解锁 locked 的直接下游；重批准时把已有产物的下游标记 stale。 */
export function refreshDownstream(_db: MockDb, project: ProjectState, lessonState: LessonState, nodeKey: string, reapproved: boolean): void {
  for (const downstreamKey of directDownstreamKeys(nodeKey)) {
    const downstream = lessonState.nodes.get(downstreamKey);
    if (!downstream) continue;
    const def = getNodeDef(downstreamKey);
    if (!def) continue;
    const depsApproved = def.dependsOn.every(
      (dep) => lessonState.nodes.get(dep)?.summary.status === "approved" || lessonState.nodes.get(dep)?.summary.status === "skipped",
    );
    if (reapproved && downstream.artifactVersions.length > 0) {
      downstream.summary.status = "stale";
      for (const version of downstream.artifactVersions) {
        if (version.status === "approved" || version.status === "needs_review") {
          version.status = "stale";
          version.stale_reason = `上游「${getNodeDef(nodeKey)?.title ?? nodeKey}」已批准新版本`;
        }
      }
      publishEvent({ event_type: "node.status_changed", project_id: project.project.project_id, lesson_id: lessonState.lesson.lesson_id, node_key: downstreamKey, task_id: null, payload: { status: "stale" } });
      continue;
    }
    if (depsApproved && downstream.summary.status === "locked") {
      downstream.summary.status = "ready";
      downstream.summary.blocker_message = null;
      publishEvent({ event_type: "node.status_changed", project_id: project.project.project_id, lesson_id: lessonState.lesson.lesson_id, node_key: downstreamKey, task_id: null, payload: { status: "ready" } });
    }
  }
}

/** 节点生成运行（拿到费用/提示词后由 handlers 调用）。 */
export function startNodeRun(input: {
  projectId: string;
  lessonId: string;
  nodeKey: string;
  promptVersionId: string | null;
  revisionInstruction?: string | null;
  estimatedCostMinor: number;
  providerName: string | null;
  itemId?: string | null;
}): Task {
  const db = getDb();
  const found = findNodeState(db, input.projectId, input.lessonId, input.nodeKey);
  const node = found?.node ?? null;
  const def = getNodeDef(input.nodeKey);
  const capability = def?.capability ?? "text_generation";
  const prevStatus = node?.summary.status ?? "ready";
  const task = startTask({
    taskType: `node_run:${input.nodeKey}`,
    projectId: input.projectId,
    lessonId: input.lessonId,
    nodeKey: input.nodeKey,
    itemId: input.itemId ?? null,
    durationMs: CAPABILITY_DURATION[capability] ?? 4000,
    estimatedCostMinor: input.estimatedCostMinor,
    actualCostMinor: Math.round(input.estimatedCostMinor * 0.92),
    providerName: input.providerName,
    longPipeline: capability === "video_generation" || capability === "video_compose",
    prevNodeStatus: prevStatus,
    onComplete: (mockDb) => {
      const location = findNodeState(mockDb, input.projectId, input.lessonId, input.nodeKey);
      if (!location?.node || !location.lessonState) return;
      const generated = generateNodeContent(mockDb, {
        project: location.project,
        lessonState: location.lessonState,
        nodeKey: input.nodeKey,
        revisionInstruction: input.revisionInstruction ?? null,
      });
      const versionNumber = location.node.artifactVersions.length > 0 ? Math.max(...location.node.artifactVersions.map((v) => v.version_number)) + 1 : 1;
      for (const version of location.node.artifactVersions) {
        if (version.status === "needs_review") version.status = "superseded";
      }
      const artifact = makeArtifact({
        artifactType: input.nodeKey,
        versionNumber,
        status: "needs_review",
        content: generated.content,
        promptVersionId: input.promptVersionId,
        createdMinutesAgo: 0,
      });
      location.node.artifactVersions.unshift(artifact);
      location.node.validationResults = generated.validation ?? [];
      location.node.summary.status = "needs_review";
      location.node.summary.progress_percent = 100;
      location.node.activeTaskId = null;
      publishEvent({ event_type: "artifact.version_created", project_id: input.projectId, lesson_id: input.lessonId, node_key: input.nodeKey, task_id: task.task_id, payload: { artifact_version_id: artifact.artifact_version_id, version_number: versionNumber } });
      publishEvent({ event_type: "node.status_changed", project_id: input.projectId, lesson_id: input.lessonId, node_key: input.nodeKey, task_id: task.task_id, payload: { status: "needs_review" } });
    },
  });
  if (node) node.activeTaskId = task.task_id;
  return task;
}

export { registerGeneratedAsset };
