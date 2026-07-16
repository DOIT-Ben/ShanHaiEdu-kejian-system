import type {
  AdminUser,
  AuditEntry,
  BudgetConfig,
  ModelDefinition,
  ModelRun,
  Organization,
  Provider,
  RoutePolicy,
  TemplateDetail,
  WorkflowVersion,
  WorkflowVersionDetail,
} from "@/shared/api/types";
import type { MockAccount, MockDb } from "../db";
import { minutesAgo } from "../db";
import { LESSON_NODES } from "@/entities/workflow/nodes";
import { promptTextForNode } from "./prompts";

/** 平台侧种子：账号、组织、网关、模板、工作流、审计。 */

export function seedAccounts(): MockAccount[] {
  return [
    {
      password: "demo1234",
      user: {
        user_id: "user_teacher_1",
        display_name: "林晓雨",
        email: "teacher@shanhai.edu",
        role: "teacher",
        organization_id: "org_1",
        organization_name: "山海实验小学",
      },
    },
    {
      password: "demo1234",
      user: {
        user_id: "user_admin_1",
        display_name: "王建国",
        email: "admin@shanhai.edu",
        role: "system_admin",
        organization_id: null,
        organization_name: null,
      },
    },
    {
      password: "demo1234",
      user: {
        user_id: "user_tpl_1",
        display_name: "赵敏芝",
        email: "template@shanhai.edu",
        role: "template_admin",
        organization_id: null,
        organization_name: null,
      },
    },
    {
      password: "demo1234",
      user: {
        user_id: "user_audit_1",
        display_name: "陈审计",
        email: "audit@shanhai.edu",
        role: "audit_admin",
        organization_id: null,
        organization_name: null,
      },
    },
  ];
}

export function seedOrganizations(): Organization[] {
  return [
    { organization_id: "org_1", name: "山海实验小学", member_count: 42 },
    { organization_id: "org_2", name: "云溪镇中心小学", member_count: 18 },
  ];
}

export function seedAdminUsers(): AdminUser[] {
  return [
    { user_id: "user_teacher_1", display_name: "林晓雨", email: "teacher@shanhai.edu", role: "teacher", status: "active", organization_id: "org_1", organization_name: "山海实验小学", last_active_at: minutesAgo(12) },
    { user_id: "user_teacher_2", display_name: "周文博", email: "zhouwb@shanhai.edu", role: "teacher", status: "active", organization_id: "org_1", organization_name: "山海实验小学", last_active_at: minutesAgo(240) },
    { user_id: "user_teacher_3", display_name: "吴桂芳", email: "wugf@yunxi.edu", role: "teacher", status: "disabled", organization_id: "org_2", organization_name: "云溪镇中心小学", last_active_at: minutesAgo(60 * 24 * 9) },
    { user_id: "user_tpl_1", display_name: "赵敏芝", email: "template@shanhai.edu", role: "template_admin", status: "active", organization_id: null, organization_name: null, last_active_at: minutesAgo(45) },
    { user_id: "user_admin_1", display_name: "王建国", email: "admin@shanhai.edu", role: "system_admin", status: "active", organization_id: null, organization_name: null, last_active_at: minutesAgo(3) },
    { user_id: "user_audit_1", display_name: "陈审计", email: "audit@shanhai.edu", role: "audit_admin", status: "active", organization_id: null, organization_name: null, last_active_at: minutesAgo(60 * 30) },
  ];
}

export function seedProviders(degraded: boolean): Provider[] {
  return [
    { provider_id: "prov_text_1", name: "启明文本云", provider_type: "text", base_url: "https://api.qiming-llm.example.com", auth_method: "api_key", enabled: true, environment: "production", health_status: "healthy", credential_status: "configured", credential_mask: "sk-****Kx3f", credential_updated_at: minutesAgo(60 * 24 * 6), timeout_seconds: 120, retry_limit: 2, concurrency_limit: 8, rate_limit_per_minute: 300 },
    { provider_id: "prov_img_1", name: "绘山图像", provider_type: "image", base_url: "https://api.huishan-image.example.com", auth_method: "api_key", enabled: true, environment: "production", health_status: degraded ? "degraded" : "healthy", credential_status: "configured", credential_mask: "hs-****9d2a", credential_updated_at: minutesAgo(60 * 24 * 20), timeout_seconds: 180, retry_limit: 2, concurrency_limit: 4, rate_limit_per_minute: 60 },
    { provider_id: "prov_video_1", name: "潮汐视频云", provider_type: "video", base_url: "https://api.tide-video.example.com", auth_method: "api_key", enabled: true, environment: "production", health_status: degraded ? "unavailable" : "healthy", credential_status: "configured", credential_mask: "tv-****7bc1", credential_updated_at: minutesAgo(60 * 24 * 3), timeout_seconds: 600, retry_limit: 1, concurrency_limit: 2, rate_limit_per_minute: 12 },
    { provider_id: "prov_video_2", name: "星河视频（备用）", provider_type: "video", base_url: "https://api.galaxy-video.example.com", auth_method: "api_key", enabled: true, environment: "production", health_status: "healthy", credential_status: "configured", credential_mask: "gx-****p0q8", credential_updated_at: minutesAgo(60 * 24 * 15), timeout_seconds: 600, retry_limit: 1, concurrency_limit: 2, rate_limit_per_minute: 10 },
    { provider_id: "prov_tts_1", name: "知音语音", provider_type: "tts", base_url: "https://api.zhiyin-tts.example.com", auth_method: "api_key", enabled: true, environment: "production", health_status: "healthy", credential_status: "expiring", credential_mask: "zy-****m4n2", credential_updated_at: minutesAgo(60 * 24 * 85), timeout_seconds: 120, retry_limit: 2, concurrency_limit: 6, rate_limit_per_minute: 120 },
    { provider_id: "prov_ppt_1", name: "内置版式引擎", provider_type: "presentation", base_url: "https://gateway.internal/pptx", auth_method: "internal", enabled: true, environment: "production", health_status: "healthy", credential_status: "configured", credential_mask: null, credential_updated_at: null, timeout_seconds: 300, retry_limit: 1, concurrency_limit: 4, rate_limit_per_minute: 30 },
  ];
}

export function seedModels(): ModelDefinition[] {
  return [
    { model_id: "model_text_std", provider_id: "prov_text_1", provider_name: "启明文本云", business_name: "教学文本·标准", upstream_name: "qiming-chat-pro", capabilities: ["text_generation"], input_modalities: ["text"], output_modalities: ["text"], constraints: { max_output_tokens: 8192 }, features: { json_mode: true }, pricing: { unit: "1k_tokens", input_minor_units: 2, output_minor_units: 6 }, recommended_scenarios: "教案、大纲、脚本类长文本生成", enabled: true },
    { model_id: "model_text_fast", provider_id: "prov_text_1", provider_name: "启明文本云", business_name: "教学文本·极速", upstream_name: "qiming-chat-lite", capabilities: ["text_generation"], input_modalities: ["text"], output_modalities: ["text"], constraints: { max_output_tokens: 4096 }, features: { json_mode: true }, pricing: { unit: "1k_tokens", input_minor_units: 1, output_minor_units: 2 }, recommended_scenarios: "快速草稿与修订", enabled: true },
    { model_id: "model_img_std", provider_id: "prov_img_1", provider_name: "绘山图像", business_name: "教学插画·标准", upstream_name: "huishan-illustration-v3", capabilities: ["image_generation"], input_modalities: ["text", "image"], output_modalities: ["image"], constraints: { max_resolution: "2048x2048" }, features: { reference_image: true }, pricing: { unit: "image", minor_units: 120 }, recommended_scenarios: "PPT 配图、分镜首帧", enabled: true },
    { model_id: "model_img_eco", provider_id: "prov_img_1", provider_name: "绘山图像", business_name: "教学插画·经济", upstream_name: "huishan-illustration-lite", capabilities: ["image_generation"], input_modalities: ["text"], output_modalities: ["image"], constraints: { max_resolution: "1024x1024" }, features: {}, pricing: { unit: "image", minor_units: 40 }, recommended_scenarios: "草稿与快速预览", enabled: true },
    { model_id: "model_video_std", provider_id: "prov_video_1", provider_name: "潮汐视频云", business_name: "教学视频·标准", upstream_name: "tide-motion-2", capabilities: ["video_generation"], input_modalities: ["text", "image"], output_modalities: ["video"], constraints: { max_duration_seconds: 20, resolution: "1080p" }, features: { first_frame: true }, pricing: { unit: "clip", minor_units: 1500 }, recommended_scenarios: "镜头片段生成", enabled: true },
    { model_id: "model_video_bak", provider_id: "prov_video_2", provider_name: "星河视频（备用）", business_name: "教学视频·备用", upstream_name: "galaxy-motion-1", capabilities: ["video_generation"], input_modalities: ["text", "image"], output_modalities: ["video"], constraints: { max_duration_seconds: 15, resolution: "1080p" }, features: { first_frame: true }, pricing: { unit: "clip", minor_units: 1800 }, recommended_scenarios: "主服务降级时的备用片段生成", enabled: true },
    { model_id: "model_tts_std", provider_id: "prov_tts_1", provider_name: "知音语音", business_name: "旁白配音·标准", upstream_name: "zhiyin-voice-kids", capabilities: ["tts"], input_modalities: ["text"], output_modalities: ["audio"], constraints: { max_chars: 5000 }, features: { srt: true }, pricing: { unit: "1k_chars", minor_units: 20 }, recommended_scenarios: "少儿内容旁白", enabled: true },
    { model_id: "model_pptx", provider_id: "prov_ppt_1", provider_name: "内置版式引擎", business_name: "PPTX 组装", upstream_name: "internal-pptx-renderer", capabilities: ["pptx_render"], input_modalities: ["structured"], output_modalities: ["file"], constraints: {}, features: {}, pricing: { unit: "document", minor_units: 0 }, recommended_scenarios: "PPT 导出", enabled: true },
    { model_id: "model_compose", provider_id: "prov_video_1", provider_name: "潮汐视频云", business_name: "视频合成", upstream_name: "tide-compose", capabilities: ["video_compose"], input_modalities: ["video", "audio"], output_modalities: ["video"], constraints: {}, features: {}, pricing: { unit: "minute", minor_units: 200 }, recommended_scenarios: "片段合成与压制", enabled: true },
  ];
}

export function seedRoutes(): RoutePolicy[] {
  return [
    { route_policy_id: "route_text", capability: "text_generation", mode: "balanced", primary_model_id: "model_text_std", fallback_model_ids: ["model_text_fast"], allow_cross_provider_fallback: false, max_cost_minor_units: 500, parameter_bounds: { temperature: [0, 1] }, scope_organization_id: null, scope_project_id: null, enabled: true, updated_at: minutesAgo(60 * 24 * 2) },
    { route_policy_id: "route_image", capability: "image_generation", mode: "quality", primary_model_id: "model_img_std", fallback_model_ids: ["model_img_eco"], allow_cross_provider_fallback: false, max_cost_minor_units: 2000, parameter_bounds: { candidate_count: [1, 4] }, scope_organization_id: null, scope_project_id: null, enabled: true, updated_at: minutesAgo(60 * 24 * 8) },
    { route_policy_id: "route_video", capability: "video_generation", mode: "quality", primary_model_id: "model_video_std", fallback_model_ids: ["model_video_bak"], allow_cross_provider_fallback: true, max_cost_minor_units: 20000, parameter_bounds: { duration_seconds: [3, 20] }, scope_organization_id: null, scope_project_id: null, enabled: true, updated_at: minutesAgo(60 * 5) },
    { route_policy_id: "route_tts", capability: "tts", mode: "balanced", primary_model_id: "model_tts_std", fallback_model_ids: [], allow_cross_provider_fallback: false, max_cost_minor_units: 500, parameter_bounds: {}, scope_organization_id: null, scope_project_id: null, enabled: true, updated_at: minutesAgo(60 * 24 * 30) },
    { route_policy_id: "route_pptx", capability: "pptx_render", mode: "fixed", primary_model_id: "model_pptx", fallback_model_ids: [], allow_cross_provider_fallback: false, max_cost_minor_units: null, parameter_bounds: {}, scope_organization_id: null, scope_project_id: null, enabled: true, updated_at: minutesAgo(60 * 24 * 30) },
    { route_policy_id: "route_compose", capability: "video_compose", mode: "fixed", primary_model_id: "model_compose", fallback_model_ids: [], allow_cross_provider_fallback: false, max_cost_minor_units: 5000, parameter_bounds: {}, scope_organization_id: null, scope_project_id: null, enabled: true, updated_at: minutesAgo(60 * 24 * 30) },
  ];
}

export function seedBudgets(): BudgetConfig {
  return {
    currency: "CNY",
    platform_daily_minor_units: 500_000,
    platform_daily_spent_minor_units: 86_400,
    teacher_quota_minor_units: 50_000,
    project_default_minor_units: 30_000,
    node_run_max_minor_units: 20_000,
    overage_policy: "require_authorization",
    organization_budgets: [
      { organization_id: "org_1", organization_name: "山海实验小学", monthly_limit_minor_units: 2_000_000, spent_minor_units: 431_200 },
      { organization_id: "org_2", organization_name: "云溪镇中心小学", monthly_limit_minor_units: 800_000, spent_minor_units: 65_000 },
    ],
    row_version: 3,
  };
}

export function seedModelRuns(projectId: string, degraded: boolean): ModelRun[] {
  const base: ModelRun[] = [
    { model_run_id: "mrun_1001", capability: "text_generation", provider_id: "prov_text_1", provider_name: "启明文本云", model_id: "model_text_std", model_name: "教学文本·标准", status: "completed", project_id: projectId, lesson_id: "lesson_a1", node_key: "lesson_plan", is_fallback: false, estimated_cost_minor_units: 90, actual_cost_minor_units: 84, duration_ms: 42_000, fallback_from_model_run_id: null, created_at: minutesAgo(60 * 26) },
    { model_run_id: "mrun_1002", capability: "text_generation", provider_id: "prov_text_1", provider_name: "启明文本云", model_id: "model_text_std", model_name: "教学文本·标准", status: "completed", project_id: projectId, lesson_id: "lesson_a1", node_key: "intro_design", is_fallback: false, estimated_cost_minor_units: 120, actual_cost_minor_units: 118, duration_ms: 55_000, fallback_from_model_run_id: null, created_at: minutesAgo(60 * 24) },
    { model_run_id: "mrun_1003", capability: "image_generation", provider_id: "prov_img_1", provider_name: "绘山图像", model_id: "model_img_std", model_name: "教学插画·标准", status: "completed", project_id: projectId, lesson_id: "lesson_a1", node_key: "video_master_image", is_fallback: false, estimated_cost_minor_units: 360, actual_cost_minor_units: 360, duration_ms: 68_000, fallback_from_model_run_id: null, created_at: minutesAgo(60 * 20) },
    { model_run_id: "mrun_1004", capability: "image_generation", provider_id: "prov_img_1", provider_name: "绘山图像", model_id: "model_img_std", model_name: "教学插画·标准", status: "completed", project_id: projectId, lesson_id: "lesson_a1", node_key: "video_image_assets", is_fallback: false, estimated_cost_minor_units: 960, actual_cost_minor_units: 840, duration_ms: 190_000, fallback_from_model_run_id: null, created_at: minutesAgo(60 * 8) },
    { model_run_id: "mrun_1005", capability: "video_generation", provider_id: "prov_video_1", provider_name: "潮汐视频云", model_id: "model_video_std", model_name: "教学视频·标准", status: "failed", project_id: projectId, lesson_id: "lesson_a1", node_key: "video_clips", is_fallback: false, estimated_cost_minor_units: 1500, actual_cost_minor_units: 0, duration_ms: 12_000, fallback_from_model_run_id: null, created_at: minutesAgo(60 * 3) },
  ];
  if (degraded) {
    base.push({ model_run_id: "mrun_1006", capability: "video_generation", provider_id: "prov_video_2", provider_name: "星河视频（备用）", model_id: "model_video_bak", model_name: "教学视频·备用", status: "completed", project_id: projectId, lesson_id: "lesson_a1", node_key: "video_clips", is_fallback: true, estimated_cost_minor_units: 1800, actual_cost_minor_units: 1800, duration_ms: 220_000, fallback_from_model_run_id: "mrun_1005", created_at: minutesAgo(60 * 2) });
  }
  return base;
}

export function seedTemplates(): Map<string, TemplateDetail> {
  const map = new Map<string, TemplateDetail>();
  const nodes = LESSON_NODES.filter((n) => n.capability && n.capability !== "pptx_render" && n.capability !== "video_compose");
  nodes.forEach((node, index) => {
    const templateId = `tpl_${node.key}`;
    map.set(templateId, {
      template: {
        template_id: templateId,
        name: `${node.title}提示词模板`,
        node_type: node.key,
        current_version: "1.2.0",
        status: index === 1 ? "candidate" : "published",
        description: `${node.title}节点的系统默认提示词模板`,
        usage_count: 40 - index * 3,
        updated_at: minutesAgo(60 * 24 * (index + 1)),
      },
      content: promptTextForNode(node.key),
      variables_schema: {
        type: "object",
        properties: {
          lesson_title: { type: "string", description: "课时标题" },
          knowledge_points: { type: "array", description: "知识点列表" },
        },
      },
      versions: [
        { version: "1.2.0", status: index === 1 ? "candidate" : "published", changelog: "优化输出结构约束，明确禁止占位内容。", created_at: minutesAgo(60 * 24 * (index + 1)) },
        { version: "1.1.0", status: "deprecated", changelog: "补充内容安全条款。", created_at: minutesAgo(60 * 24 * (index + 12)) },
        { version: "1.0.0", status: "deprecated", changelog: "初始版本。", created_at: minutesAgo(60 * 24 * (index + 30)) },
      ],
      bindings: [{ node_type: node.key, workflow_version: "wf-primary-math@2.0", scope: null }],
      validation_results: [
        { rule_id: "vars_resolved", severity: "error", passed: true, message: "模板变量均可解析" },
        { rule_id: "safety_clause", severity: "warning", passed: index !== 1, message: index === 1 ? "候选版本缺少内容安全条款，发布前需补充" : "包含内容安全条款", action: index === 1 ? "编辑模板补充安全条款" : null },
      ],
    });
  });
  return map;
}

export function seedWorkflows(): { list: WorkflowVersion[]; details: Map<string, WorkflowVersionDetail> } {
  const wf: WorkflowVersion = {
    workflow_id: "wf_primary_math",
    name: "小学数学课件生产流程",
    version: "2.0",
    status: "published",
    node_count: LESSON_NODES.length,
    bound_project_count: 3,
    published_at: minutesAgo(60 * 24 * 14),
  };
  const draft: WorkflowVersion = {
    workflow_id: "wf_primary_math_next",
    name: "小学数学课件生产流程",
    version: "2.1-draft",
    status: "draft",
    node_count: LESSON_NODES.length,
    bound_project_count: 0,
    published_at: null,
  };
  const details = new Map<string, WorkflowVersionDetail>();
  for (const version of [wf, draft]) {
    details.set(version.workflow_id, {
      workflow: version,
      nodes: LESSON_NODES.map((n) => ({
        node_key: n.key,
        title: n.title,
        group: n.group,
        capability: n.capability,
        depends_on: n.dependsOn,
        skippable: n.skippable,
      })),
    });
  }
  return { list: [wf, draft], details };
}

export function seedAudit(): AuditEntry[] {
  return [
    { audit_id: "audit_1", actor_name: "王建国", actor_role: "system_admin", action: "provider.update", object_type: "provider", object_id: "prov_video_1", summary: "更新潮汐视频云超时时间 300s → 600s", occurred_at: minutesAgo(60 * 5), trace_id: "trace_a1" },
    { audit_id: "audit_2", actor_name: "赵敏芝", actor_role: "template_admin", action: "template.publish", object_type: "template", object_id: "tpl_lesson_plan", summary: "发布教案模板 1.2.0", occurred_at: minutesAgo(60 * 24), trace_id: "trace_a2" },
    { audit_id: "audit_3", actor_name: "林晓雨", actor_role: "teacher", action: "artifact.approve", object_type: "artifact_version", object_id: "av_division", summary: "批准课时划分 v2", occurred_at: minutesAgo(60 * 30), trace_id: "trace_a3" },
    { audit_id: "audit_4", actor_name: "王建国", actor_role: "system_admin", action: "budget.update", object_type: "budget", object_id: "platform", summary: "调整平台日预算 4000 → 5000 元", occurred_at: minutesAgo(60 * 24 * 2), trace_id: "trace_a4" },
    { audit_id: "audit_5", actor_name: "王建国", actor_role: "system_admin", action: "user.disable", object_type: "user", object_id: "user_teacher_3", summary: "停用云溪镇账号（教师调离）", occurred_at: minutesAgo(60 * 24 * 5), trace_id: "trace_a5" },
  ];
}

export function applyPlatformSeed(db: MockDb): void {
  db.accounts = seedAccounts();
  db.organizations = seedOrganizations();
  db.users = seedAdminUsers();
  db.providers = seedProviders(Boolean(db.flags.providerDegraded || db.flags.paidFallbackConfirm));
  db.models = seedModels();
  db.routes = seedRoutes();
  db.budgets = seedBudgets();
  db.audit = seedAudit();
  db.templates = seedTemplates();
  const wf = seedWorkflows();
  db.workflows = wf.list;
  db.workflowDetails = wf.details;
}
