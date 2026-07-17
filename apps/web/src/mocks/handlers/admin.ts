import { http } from "msw";
import { db, nextId, nowIso } from "../db";
import { API, checkIfMatch, fail, idempotent, notFound, ok, requireAdmin, simulateLatency } from "../http";
import { startJob } from "../engine";
import type { ContentDefinition } from "@/entities/content/definition";

function contentPackagePayload(pkg: NonNullable<ReturnType<typeof db.contentPackages.get>>) {
  return {
    id: pkg.id,
    title: pkg.title,
    domain: pkg.domain,
    status: pkg.status,
    current_version_no: pkg.current_version_no,
    definition_key: pkg.definition_key,
    updated_at: pkg.updated_at,
  };
}

function providerPayload(provider: NonNullable<ReturnType<typeof db.providers.get>>) {
  return {
    id: provider.id,
    display_name: provider.display_name,
    capabilities: provider.capabilities,
    base_url: provider.base_url,
    enabled: provider.enabled,
    secret_status: provider.secret_status,
    secret_tail: provider.secret_tail,
    last_test: provider.last_test,
    updated_at: provider.updated_at,
  };
}

/** 管理端：内容中心、工作流、模型服务（密钥仅状态+尾号）、运行费用、用户、审计。 */
export const adminHandlers = [
  // ── 内容中心 ─────────────────────────────────────────
  http.get(API("/admin/content-packages"), async () => {
    await simulateLatency(120);
    const denied = requireAdmin();
    if (denied) return denied;
    const items = [...db.contentPackages.values()]
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .map(contentPackagePayload);
    return ok({ items }, { meta: { next_cursor: null } });
  }),

  http.post(API("/admin/content-packages"), async ({ request }) => {
    await simulateLatency(200);
    const denied = requireAdmin();
    if (denied) return denied;
    const body = (await request.json()) as {
      title?: string;
      domain?: "lesson_plan" | "intro_options" | "ppt" | "video" | "quality" | "style" | "prompt";
      definition?: ContentDefinition;
    };
    if (!body.title || !body.domain || !body.definition) {
      return fail(422, "VALIDATION_FAILED", "缺少标题、域或内容定义。");
    }
    return idempotent(request, `content-import:${body.title}`, () => {
      const id = nextId();
      db.contentPackages.set(id, {
        id,
        title: body.title!,
        domain: body.domain!,
        status: "checking",
        current_version_no: 0,
        definition_key: body.definition!.definition_key,
        definition: body.definition!,
        validation_issues: [],
        versions: [],
        test_cases: [
          { key: "tc-structure", title: "结构完整性", status: "pending" },
          { key: "tc-render", title: "教师端渲染预览", status: "pending" },
        ],
        usage: [],
        updated_at: nowIso(),
      });
      const job = startJob({
        kind: "content_check",
        title: `系统检查：${body.title}`,
        phaseMs: [500, 1600],
        onComplete: () => {
          const pkg = db.contentPackages.get(id);
          if (!pkg) return;
          pkg.status = "draft";
          pkg.test_cases = pkg.test_cases.map((tc) =>
            tc.key === "tc-structure" ? { ...tc, status: "passed" } : tc,
          );
          pkg.updated_at = nowIso();
        },
      });
      return {
        data: { job_id: job.id, status: "queued" as const, events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
        status: 202,
      };
    });
  }),

  http.get(API("/admin/content-packages/:contentPackageId"), async ({ params }) => {
    await simulateLatency(110);
    const denied = requireAdmin();
    if (denied) return denied;
    const pkg = db.contentPackages.get(params.contentPackageId as string);
    if (!pkg) return notFound("内容包");
    return ok({
      package: contentPackagePayload(pkg),
      definition: pkg.definition,
      validation_issues: pkg.validation_issues,
      versions: pkg.versions,
      test_cases: pkg.test_cases,
      usage: pkg.usage,
    });
  }),

  http.post(API("/admin/content-packages/:contentPackageId/dry-run"), async ({ params, request }) => {
    await simulateLatency(180);
    const denied = requireAdmin();
    if (denied) return denied;
    const pkg = db.contentPackages.get(params.contentPackageId as string);
    if (!pkg) return notFound("内容包");
    if (pkg.status === "checking") {
      return fail(409, "PACKAGE_CHECKING", "系统检查未完成。");
    }
    return idempotent(request, `dry-run:${pkg.id}:${pkg.updated_at}`, () => {
      const job = startJob({
        kind: "content_dry_run",
        title: `试运行：${pkg.title}`,
        phaseMs: [700, 2400],
        onComplete: () => {
          pkg.status = "dry_run";
          pkg.test_cases = pkg.test_cases.map((tc) => ({ ...tc, status: "passed" as const }));
          pkg.updated_at = nowIso();
        },
      });
      return {
        data: { job_id: job.id, status: "queued" as const, events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
        status: 202,
      };
    });
  }),

  http.post(API("/admin/content-packages/:contentPackageId/publish"), async ({ params, request }) => {
    await simulateLatency(200);
    const denied = requireAdmin();
    if (denied) return denied;
    const pkg = db.contentPackages.get(params.contentPackageId as string);
    if (!pkg) return notFound("内容包");
    if (pkg.status !== "dry_run" && pkg.status !== "published") {
      return fail(409, "DRY_RUN_REQUIRED", "发布前必须通过试运行。");
    }
    const failing = pkg.test_cases.find((tc) => tc.status !== "passed");
    if (failing) {
      return fail(409, "TEST_CASES_FAILING", `测试案例「${failing.title}」未通过。`);
    }
    return idempotent(request, `publish:${pkg.id}:${pkg.current_version_no + 1}`, () => {
      pkg.current_version_no += 1;
      pkg.status = "published";
      pkg.versions = [
        { version_no: pkg.current_version_no, published_at: nowIso(), note: null },
        ...pkg.versions,
      ];
      pkg.updated_at = nowIso();
      db.auditEvents.unshift({
        id: nextId(),
        actor_name: db.users.find((u) => u.id === db.sessionUserId)?.name ?? "管理员",
        action: "content_package.publish",
        resource_label: `${pkg.title} v${pkg.current_version_no}`,
        detail: null,
        occurred_at: nowIso(),
      });
      return {
        data: {
          package: contentPackagePayload(pkg),
          definition: pkg.definition,
          validation_issues: pkg.validation_issues,
          versions: pkg.versions,
          test_cases: pkg.test_cases,
          usage: pkg.usage,
        },
        status: 201,
      };
    });
  }),

  // ── 工作流 ───────────────────────────────────────────
  http.get(API("/admin/workflows"), async () => {
    await simulateLatency(110);
    const denied = requireAdmin();
    if (denied) return denied;
    return ok({
      items: [
        {
          id: db.scenario === "default" ? "00000000-0000-4000-8000-000000000950" : "00000000-0000-4000-8000-000000000950",
          key: "primary_math_end_to_end",
          title: "小学数学端到端制作流程",
          status: "published" as const,
          version_no: 4,
          node_count: 13,
          updated_at: "2026-07-15T06:00:00Z",
        },
      ],
    });
  }),

  http.get(API("/admin/workflows/:workflowId"), async ({ params }) => {
    await simulateLatency(120);
    const denied = requireAdmin();
    if (denied) return denied;
    void params;
    return ok({
      workflow: {
        id: "00000000-0000-4000-8000-000000000950",
        key: "primary_math_end_to_end",
        title: "小学数学端到端制作流程",
        status: "published" as const,
        version_no: 4,
        node_count: 13,
        updated_at: "2026-07-15T06:00:00Z",
      },
      nodes: [
        { node_key: "lesson_plan", title: "教案", capability: "text", depends_on: [], human_gate: true, skippable: false, context_whitelist: ["material_scope", "content_definition"], budget_minor_units: 300, retry_limit: 2 },
        { node_key: "intro_options", title: "三类九套导入设计", capability: "text", depends_on: [], human_gate: true, skippable: true, context_whitelist: ["lesson_scope"], budget_minor_units: 400, retry_limit: 2 },
        { node_key: "intro_selection", title: "导入方案选择", capability: "none", depends_on: ["intro_options"], human_gate: true, skippable: true, context_whitelist: [], budget_minor_units: null, retry_limit: null },
        { node_key: "ppt_outline", title: "PPT 大纲", capability: "text", depends_on: ["lesson_plan"], human_gate: true, skippable: false, context_whitelist: ["approved_lesson_plan"], budget_minor_units: 200, retry_limit: 2 },
        { node_key: "ppt_cover", title: "PPT 封面", capability: "image", depends_on: ["ppt_outline"], human_gate: true, skippable: false, context_whitelist: ["ppt_outline"], budget_minor_units: 600, retry_limit: 3 },
        { node_key: "ppt_body", title: "PPT 正文", capability: "image", depends_on: ["ppt_cover"], human_gate: true, skippable: false, context_whitelist: ["ppt_outline", "ppt_style_contract"], budget_minor_units: 1800, retry_limit: 3 },
        { node_key: "ppt_export", title: "PPT 导出", capability: "layout", depends_on: ["ppt_body"], human_gate: false, skippable: false, context_whitelist: ["approved_pages"], budget_minor_units: null, retry_limit: 2 },
        { node_key: "video_script", title: "母版剧本", capability: "text", depends_on: ["intro_selection"], human_gate: true, skippable: false, context_whitelist: ["intro_snapshot"], budget_minor_units: 300, retry_limit: 2 },
        { node_key: "video_storyboard", title: "粗分镜", capability: "text", depends_on: ["video_script"], human_gate: true, skippable: false, context_whitelist: ["master_script"], budget_minor_units: 300, retry_limit: 2 },
        { node_key: "video_style", title: "画面风格", capability: "image", depends_on: ["video_storyboard"], human_gate: true, skippable: false, context_whitelist: ["storyboard"], budget_minor_units: 600, retry_limit: 3 },
        { node_key: "video_assets", title: "镜头图片", capability: "image", depends_on: ["video_style"], human_gate: true, skippable: false, context_whitelist: ["storyboard", "video_style_contract"], budget_minor_units: 2400, retry_limit: 3 },
        { node_key: "video_clips", title: "视频片段", capability: "video", depends_on: ["video_assets"], human_gate: true, skippable: false, context_whitelist: ["fine_storyboard", "approved_assets"], budget_minor_units: 6000, retry_limit: 3 },
        { node_key: "video_compose", title: "视频合成", capability: "video", depends_on: ["video_clips"], human_gate: true, skippable: false, context_whitelist: ["timeline"], budget_minor_units: 800, retry_limit: 2 },
      ],
      checks: [],
    });
  }),

  // ── 模型服务 ─────────────────────────────────────────
  http.get(API("/admin/model-services/overview"), async () => {
    await simulateLatency(120);
    const denied = requireAdmin();
    if (denied) return denied;
    return ok({
      today: {
        run_count: 86,
        success_rate_percent: 94.2,
        average_duration_ms: 8600,
        cost_minor_units: 12480,
        currency: "CNY",
      },
      backlog_count: 3,
      degraded: [
        {
          provider_id: db.providers.keys().next().value as string,
          provider_name: "知音语音",
          reason: "密钥即将过期（7 天内）",
        },
      ],
      capability_primaries: [
        { capability: "text", provider_name: "启明文本云", model_name: "qiming-pro-2", fallback_provider_name: null },
        { capability: "image", provider_name: "绘山图像", model_name: "huishan-xl", fallback_provider_name: null },
        { capability: "video", provider_name: "潮汐视频云", model_name: "tide-motion-3", fallback_provider_name: "星河视频（备用）" },
        { capability: "tts", provider_name: "知音语音", model_name: "zhiyin-warm", fallback_provider_name: null },
        { capability: "layout", provider_name: "内置版式引擎", model_name: "layout-v2", fallback_provider_name: null },
      ],
    });
  }),

  http.get(API("/admin/providers"), async () => {
    await simulateLatency(110);
    const denied = requireAdmin();
    if (denied) return denied;
    const items = [...db.providers.values()].map(providerPayload);
    return ok({ items });
  }),

  http.patch(API("/admin/providers/:providerId"), async ({ params, request }) => {
    await simulateLatency(160);
    const denied = requireAdmin();
    if (denied) return denied;
    const provider = db.providers.get(params.providerId as string);
    if (!provider) return notFound("模型服务");
    const conflict = checkIfMatch(request, provider.etag);
    if (conflict) return conflict;
    const body = (await request.json()) as Partial<{
      display_name: string;
      base_url: string;
      secret: string;
      enabled: boolean;
    }>;
    return idempotent(request, `provider:${provider.id}:${JSON.stringify({ ...body, secret: body.secret ? "***" : undefined })}`, () => {
      if (body.display_name) provider.display_name = body.display_name;
      if (body.base_url) provider.base_url = body.base_url;
      if (body.enabled !== undefined) provider.enabled = body.enabled;
      if (body.secret) {
        // 密钥只写：仅更新状态与尾号，绝不回显
        provider.secret_status = "configured";
        provider.secret_tail = body.secret.slice(-4);
      }
      provider.updated_at = nowIso();
      provider.etag += 1;
      db.auditEvents.unshift({
        id: nextId(),
        actor_name: db.users.find((u) => u.id === db.sessionUserId)?.name ?? "管理员",
        action: "provider.update",
        resource_label: provider.display_name,
        detail: body.secret ? `更新密钥（尾号 ${provider.secret_tail}）` : "更新配置",
        occurred_at: nowIso(),
      });
      return { data: providerPayload(provider), etag: provider.etag };
    });
  }),

  http.post(API("/admin/providers/:providerId/test"), async ({ params, request }) => {
    await simulateLatency(140);
    const denied = requireAdmin();
    if (denied) return denied;
    const provider = db.providers.get(params.providerId as string);
    if (!provider) return notFound("模型服务");
    return idempotent(request, `provider-test:${provider.id}:${provider.updated_at}`, () => {
      const job = startJob({
        kind: "provider_test",
        title: `连接测试：${provider.display_name}`,
        phaseMs: [400, 1400],
        onComplete: () => {
          provider.last_test = {
            status: provider.secret_status === "missing" ? "failed" : "passed",
            tested_at: nowIso(),
            detail: provider.secret_status === "missing" ? "未配置密钥" : null,
          };
          provider.updated_at = nowIso();
          provider.etag += 1;
        },
      });
      return {
        data: { job_id: job.id, status: "queued" as const, events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
        status: 202,
      };
    });
  }),

  http.get(API("/admin/models"), async () => {
    await simulateLatency(110);
    const denied = requireAdmin();
    if (denied) return denied;
    const providerByCapability = (cap: string) =>
      [...db.providers.values()].filter((p) => (p.capabilities as string[]).includes(cap));
    const items = [
      ...providerByCapability("text").map((p, i) => ({
        id: `00000000-0000-4000-8000-9000000000${10 + i}`,
        provider_id: p.id,
        provider_name: p.display_name,
        capability: "text" as const,
        model_name: "qiming-pro-2",
        role: "primary" as const,
        concurrency_limit: 8,
        timeout_ms: 60_000,
        unit_cost_label: "约 ¥0.03 / 千字",
      })),
      ...providerByCapability("image").map((p, i) => ({
        id: `00000000-0000-4000-8000-9000000000${20 + i}`,
        provider_id: p.id,
        provider_name: p.display_name,
        capability: "image" as const,
        model_name: "huishan-xl",
        role: "primary" as const,
        concurrency_limit: 4,
        timeout_ms: 120_000,
        unit_cost_label: "约 ¥0.5 / 张",
      })),
      ...providerByCapability("video").map((p, i) => ({
        id: `00000000-0000-4000-8000-9000000000${30 + i}`,
        provider_id: p.id,
        provider_name: p.display_name,
        capability: "video" as const,
        model_name: i === 0 ? "tide-motion-3" : "galaxy-motion-1",
        role: i === 0 ? ("primary" as const) : ("fallback" as const),
        concurrency_limit: 2,
        timeout_ms: 600_000,
        unit_cost_label: "约 ¥6 / 10 秒",
      })),
      ...providerByCapability("tts").map((p, i) => ({
        id: `00000000-0000-4000-8000-9000000000${40 + i}`,
        provider_id: p.id,
        provider_name: p.display_name,
        capability: "tts" as const,
        model_name: "zhiyin-warm",
        role: "primary" as const,
        concurrency_limit: 6,
        timeout_ms: 60_000,
        unit_cost_label: "约 ¥0.2 / 分钟",
      })),
      ...providerByCapability("layout").map((p, i) => ({
        id: `00000000-0000-4000-8000-9000000000${50 + i}`,
        provider_id: p.id,
        provider_name: p.display_name,
        capability: "layout" as const,
        model_name: "layout-v2",
        role: "primary" as const,
        concurrency_limit: 4,
        timeout_ms: 120_000,
        unit_cost_label: null,
      })),
    ];
    return ok({ items });
  }),

  // ── 运行与费用 ───────────────────────────────────────
  http.get(API("/admin/usage/overview"), async () => {
    await simulateLatency(120);
    const denied = requireAdmin();
    if (denied) return denied;
    return ok({
      daily: [
        { date: "2026-07-11", run_count: 42, failed_count: 2, cost_minor_units: 6800 },
        { date: "2026-07-12", run_count: 61, failed_count: 3, cost_minor_units: 10400 },
        { date: "2026-07-13", run_count: 38, failed_count: 1, cost_minor_units: 5400 },
        { date: "2026-07-14", run_count: 74, failed_count: 6, cost_minor_units: 15800 },
        { date: "2026-07-15", run_count: 90, failed_count: 4, cost_minor_units: 18200 },
        { date: "2026-07-16", run_count: 66, failed_count: 2, cost_minor_units: 11900 },
        { date: "2026-07-17", run_count: 86, failed_count: 5, cost_minor_units: 12480 },
      ],
      currency: "CNY",
      alerts: [
        { kind: "provider_degraded" as const, message: "知音语音密钥将在 7 天内过期。", action_url: "/admin/models" },
        { kind: "failure_rate" as const, message: "视频能力今日失败率 8%，高于 5% 阈值。", action_url: "/admin/usage" },
      ],
    });
  }),

  http.get(API("/admin/model-runs"), async ({ request }) => {
    await simulateLatency(120);
    const denied = requireAdmin();
    if (denied) return denied;
    const url = new URL(request.url);
    const status = url.searchParams.get("status");
    const base = [
      { id: "00000000-0000-4000-8000-910000000001", capability: "video", provider_name: "潮汐视频云", model_name: "tide-motion-3", status: "succeeded" as const, duration_ms: 42_000, cost_minor_units: 620, project_title: "认识几分之几", error_code: null, started_at: "2026-07-17T02:12:00Z" },
      { id: "00000000-0000-4000-8000-910000000002", capability: "video", provider_name: "潮汐视频云", model_name: "tide-motion-3", status: "failed" as const, duration_ms: 38_000, cost_minor_units: 0, project_title: "认识几分之几", error_code: "PROVIDER_QUALITY_REJECT", started_at: "2026-07-17T02:20:00Z" },
      { id: "00000000-0000-4000-8000-910000000003", capability: "image", provider_name: "绘山图像", model_name: "huishan-xl", status: "succeeded" as const, duration_ms: 9_200, cost_minor_units: 50, project_title: "认识几分之几", error_code: null, started_at: "2026-07-17T02:30:00Z" },
      { id: "00000000-0000-4000-8000-910000000004", capability: "text", provider_name: "启明文本云", model_name: "qiming-pro-2", status: "succeeded" as const, duration_ms: 6_400, cost_minor_units: 12, project_title: "小数的初步认识", error_code: null, started_at: "2026-07-17T03:00:00Z" },
      { id: "00000000-0000-4000-8000-910000000005", capability: "image", provider_name: "绘山图像", model_name: "huishan-xl", status: "running" as const, duration_ms: null, cost_minor_units: null, project_title: "小数的初步认识", error_code: null, started_at: "2026-07-17T03:10:00Z" },
    ];
    const items = base.filter((run) => !status || run.status === status);
    return ok({ items }, { meta: { next_cursor: null } });
  }),

  // ── 用户与审计 ───────────────────────────────────────
  http.get(API("/admin/users"), async () => {
    await simulateLatency(110);
    const denied = requireAdmin();
    if (denied) return denied;
    const items = db.users.map((user) => ({
      id: user.id,
      name: user.name,
      email: user.email,
      roles: user.roles,
      status: "active" as const,
      last_active_at: "2026-07-17T01:00:00Z",
    }));
    return ok({ items }, { meta: { next_cursor: null } });
  }),

  http.get(API("/admin/audit-events"), async ({ request }) => {
    await simulateLatency(120);
    const denied = requireAdmin();
    if (denied) return denied;
    const url = new URL(request.url);
    const action = url.searchParams.get("action");
    const items = db.auditEvents
      .filter((event) => !action || event.action.includes(action))
      .slice(0, 50);
    return ok({ items }, { meta: { next_cursor: null } });
  }),
];
