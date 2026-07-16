import type { ScenarioFlags } from "./db";

/**
 * 场景注册表：ID 与 contracts/mock-scenarios.json 一一对应。
 * seedStage 控制种子数据形态，flags 控制接口行为。
 */
export type SeedStage = "default" | "empty";

export interface ScenarioDefinition {
  id: string;
  group: string;
  description: string;
  seedStage: SeedStage;
  flags: ScenarioFlags;
}

export const DEFAULT_SCENARIO_ID = "projects.multiple";

export const SCENARIOS: ScenarioDefinition[] = [
  { id: "auth.login.success", group: "auth", description: "教师登录成功并获得CSRF Token", seedStage: "default", flags: {} },
  { id: "auth.login.failure", group: "auth", description: "账号或密码错误", seedStage: "default", flags: { loginAlwaysFail: true } },
  { id: "auth.session.expired", group: "auth", description: "会话过期并跳转登录", seedStage: "default", flags: { sessionExpiredOnFirstMe: true } },
  { id: "projects.empty", group: "projects", description: "首次登录没有项目", seedStage: "empty", flags: { emptyProjects: true } },
  { id: "projects.multiple", group: "projects", description: "多个教材项目和不同进度", seedStage: "default", flags: {} },
  { id: "textbook.upload.running", group: "sources", description: "教材上传和解析进度", seedStage: "default", flags: { textbookUploadRunning: true } },
  { id: "textbook.parse.partial", group: "sources", description: "教材部分页面需要人工确认", seedStage: "default", flags: { evidencePartial: true } },
  { id: "textbook.parse.failed", group: "sources", description: "教材解析失败且可重试", seedStage: "default", flags: { parseFails: true } },
  { id: "lesson_division.review", group: "lessons", description: "课时划分待审核并支持编辑", seedStage: "default", flags: {} },
  { id: "lesson_division.conflict", group: "lessons", description: "保存课时划分发生409版本冲突", seedStage: "default", flags: { divisionConflictOnSave: true } },
  { id: "lesson_plan.streaming", group: "lesson_plan", description: "十二部分教案生成中", seedStage: "default", flags: { lessonPlanStreaming: true } },
  { id: "lesson_plan.review", group: "lesson_plan", description: "教案待审核、校验和版本比较", seedStage: "default", flags: {} },
  { id: "intro_design.nine_ready", group: "intro_design", description: "科普、应用和故事各三套完整", seedStage: "default", flags: {} },
  { id: "intro_design.anchor_failed", group: "intro_design", description: "独立创意通过但课程锚点失败", seedStage: "default", flags: { anchorFailed: true } },
  { id: "ppt.key_sample_review", group: "ppt", description: "PPT关键样张待批准", seedStage: "default", flags: {} },
  { id: "ppt.export.running", group: "ppt", description: "PPTX后台组装和质量检查", seedStage: "default", flags: { pptExportRunning: true } },
  { id: "video.storyboard.review", group: "video", description: "粗分镜和细分镜审核", seedStage: "default", flags: {} },
  { id: "video.shot.partial_failure", group: "video", description: "部分镜头候选成功、一个镜头失败", seedStage: "default", flags: { imagePartialFail: true, clipPartialFail: true } },
  { id: "video.clip.approval", group: "video", description: "多个clip候选中批准一个", seedStage: "default", flags: { clipApprovalReady: true } },
  { id: "video.final.processing", group: "video", description: "音频字幕和最终剪辑处理中", seedStage: "default", flags: { videoFinalProcessing: true } },
  { id: "tasks.sse.reconnect", group: "tasks", description: "SSE断线、重连并恢复最后事件", seedStage: "default", flags: { sseDropAfterMs: 8000 } },
  { id: "tasks.polling.fallback", group: "tasks", description: "SSE连续失败后轮询降级", seedStage: "default", flags: { sseAlwaysFail: true } },
  { id: "budget.authorization_required", group: "gateway", description: "预计费用超预算，需要授权", seedStage: "default", flags: { budgetAuthRequired: true } },
  { id: "provider.degraded", group: "gateway", description: "主Provider降级并展示备用模型", seedStage: "default", flags: { providerDegraded: true } },
  { id: "provider.paid_fallback_confirmation", group: "gateway", description: "视频付费任务后切换Provider需要确认", seedStage: "default", flags: { paidFallbackConfirm: true } },
  { id: "artifact.stale", group: "artifacts", description: "上游批准版本变化导致下游失效", seedStage: "default", flags: { staleDownstream: true } },
  { id: "delivery.blocked", group: "delivery", description: "缺少批准视频片段导致交付阻断", seedStage: "default", flags: { deliveryBlocked: true } },
  { id: "delivery.completed", group: "delivery", description: "交付包完成并提供短期下载授权", seedStage: "default", flags: { deliveryCompleted: true } },
];

export const scenarioById: ReadonlyMap<string, ScenarioDefinition> = new Map(
  SCENARIOS.map((s) => [s.id, s]),
);

export function resolveScenario(id: string | null | undefined): ScenarioDefinition {
  if (id) {
    const found = scenarioById.get(id);
    if (found) return found;
  }
  const fallback = scenarioById.get(DEFAULT_SCENARIO_ID);
  if (!fallback) throw new Error("默认 Mock 场景缺失");
  return fallback;
}
