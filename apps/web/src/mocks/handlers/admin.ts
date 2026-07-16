import { http } from "msw";
import type { Provider, TemplateDetail } from "@/shared/api/types";
import { getDb, minutesAgo, nextId } from "../db";
import { startTask } from "../engine";
import { api, adminGuard, fail, ok, paginate, simulateLatency } from "./http";

function maskCredential(value: string): string {
  const tail = value.slice(-4);
  return `${value.slice(0, 2)}-****${tail}`;
}

export const adminHandlers = [
  // ---------- Prompt 模板 ----------
  http.get(api("/admin/templates"), async ({ request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const url = new URL(request.url);
    const status = url.searchParams.get("status");
    const nodeType = url.searchParams.get("node_type");
    const keyword = url.searchParams.get("keyword")?.trim();
    let items = [...db.templates.values()].map((t) => t.template);
    if (status) items = items.filter((t) => t.status === status);
    if (nodeType) items = items.filter((t) => t.node_type === nodeType);
    if (keyword) items = items.filter((t) => t.name.includes(keyword));
    return ok(items);
  }),

  http.post(api("/admin/templates"), async ({ request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const body = (await request.json()) as { name?: string; node_type?: string; content?: string; variables_schema?: Record<string, unknown> };
    if (!body.name?.trim() || !body.content?.trim()) {
      return fail(422, "VALIDATION_FAILED", "模板名称与内容不能为空。", {
        details: { field_errors: { ...(body.name?.trim() ? {} : { name: "名称不能为空" }), ...(body.content?.trim() ? {} : { content: "模板内容不能为空" }) } },
      });
    }
    const templateId = nextId(db, "tpl_import");
    const detail: TemplateDetail = {
      template: {
        template_id: templateId,
        name: body.name.trim(),
        node_type: body.node_type ?? "lesson_plan",
        current_version: "0.1.0",
        status: "draft",
        description: "导入的模板草稿",
        usage_count: 0,
        updated_at: minutesAgo(0),
      },
      content: body.content,
      variables_schema: body.variables_schema ?? {},
      versions: [{ version: "0.1.0", status: "draft", changelog: "导入初始版本", created_at: minutesAgo(0) }],
      bindings: [],
      validation_results: [
        { rule_id: "vars_resolved", severity: "error", passed: !body.content.includes("{{unknown"), message: body.content.includes("{{unknown") ? "存在无法解析的模板变量" : "模板变量均可解析" },
        { rule_id: "safety_clause", severity: "warning", passed: body.content.includes("安全"), message: body.content.includes("安全") ? "包含内容安全条款" : "缺少内容安全条款，发布前需补充", action: body.content.includes("安全") ? null : "编辑模板补充安全条款" },
      ],
    };
    db.templates.set(templateId, detail);
    return ok(detail, { status: 201 });
  }),

  http.get(api("/admin/templates/:templateId"), async ({ params }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const detail = getDb().templates.get(String(params.templateId));
    if (!detail) return fail(404, "NOT_FOUND", "模板不存在。");
    return ok(detail);
  }),

  http.patch(api("/admin/templates/:templateId"), async ({ params, request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const detail = getDb().templates.get(String(params.templateId));
    if (!detail) return fail(404, "NOT_FOUND", "模板不存在。");
    const body = (await request.json()) as { content?: string; name?: string; description?: string };
    if (typeof body.content === "string") {
      detail.content = body.content;
      detail.validation_results = [
        { rule_id: "vars_resolved", severity: "error", passed: true, message: "模板变量均可解析" },
        { rule_id: "safety_clause", severity: "warning", passed: body.content.includes("安全"), message: body.content.includes("安全") ? "包含内容安全条款" : "缺少内容安全条款，发布前需补充", action: body.content.includes("安全") ? null : "编辑模板补充安全条款" },
      ];
    }
    if (typeof body.name === "string" && body.name.trim()) detail.template.name = body.name.trim();
    if (typeof body.description === "string") detail.template.description = body.description;
    detail.template.updated_at = minutesAgo(0);
    return ok(detail);
  }),

  http.post(api("/admin/templates/:templateId/dry-runs"), async ({ params }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const detail = db.templates.get(String(params.templateId));
    if (!detail) return fail(404, "NOT_FOUND", "模板不存在。");
    const task = startTask({
      taskType: "template_dry_run",
      projectId: "proj_alpha",
      durationMs: 5000,
      providerName: "启明文本云",
      onComplete: () => {
        detail.validation_results = [
          ...detail.validation_results.filter((v) => v.rule_id !== "dry_run"),
          { rule_id: "dry_run", severity: "info", passed: true, message: "试运行完成：输出结构符合节点 Schema（样例输出见运行记录）。" },
        ];
      },
    });
    return ok(task, { status: 202 });
  }),

  http.post(api("/admin/templates/:templateId/publish"), async ({ params, request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const detail = getDb().templates.get(String(params.templateId));
    if (!detail) return fail(404, "NOT_FOUND", "模板不存在。");
    const blocking = detail.validation_results.filter((v) => !v.passed && v.severity === "error");
    if (blocking.length > 0) {
      return fail(422, "VALIDATION_BLOCKING", `模板存在未通过的校验：${blocking[0].message}`, { action: "fix_validation" });
    }
    const warnings = detail.validation_results.filter((v) => !v.passed && v.severity === "warning");
    const body = (await request.json().catch(() => ({}))) as { version?: string; changelog?: string; override_reason?: string };
    if (warnings.length > 0 && !body.override_reason) {
      return fail(422, "WARNINGS_UNCONFIRMED", `存在校验警告：${warnings[0].message}。请补充说明后发布。`, { action: "confirm_warnings" });
    }
    const version = body.version ?? "1.3.0";
    detail.template.current_version = version;
    detail.template.status = "published";
    detail.template.updated_at = minutesAgo(0);
    detail.versions.unshift({ version, status: "published", changelog: body.changelog ?? "发布新版本", created_at: minutesAgo(0) });
    for (const v of detail.versions.slice(1)) {
      if (v.status === "published") v.status = "deprecated";
    }
    return ok(detail);
  }),

  http.post(api("/admin/templates/:templateId/rollback"), async ({ params, request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const detail = getDb().templates.get(String(params.templateId));
    if (!detail) return fail(404, "NOT_FOUND", "模板不存在。");
    const body = (await request.json()) as { target_version?: string; reason?: string };
    const target = detail.versions.find((v) => v.version === body.target_version);
    if (!target) return fail(404, "NOT_FOUND", "目标版本不存在。");
    if (!body.reason?.trim()) {
      return fail(422, "VALIDATION_FAILED", "回滚必须填写原因（将进入审计记录）。", { details: { field_errors: { reason: "原因不能为空" } } });
    }
    detail.template.current_version = target.version;
    target.status = "published";
    detail.template.updated_at = minutesAgo(0);
    return ok(detail);
  }),

  // ---------- 模型网关 ----------
  http.get(api("/admin/model-gateway/overview"), async () => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const completed = db.modelRuns.filter((r) => r.status === "completed");
    const failed = db.modelRuns.filter((r) => r.status === "failed");
    const finished = completed.length + failed.length;
    return ok({
      providers: db.providers,
      today: {
        run_count: db.modelRuns.length,
        success_rate_percent: finished > 0 ? Math.round((completed.length / finished) * 100) : 100,
        average_duration_ms:
          completed.length > 0
            ? Math.round(completed.reduce((sum, r) => sum + (r.duration_ms ?? 0), 0) / completed.length)
            : 0,
        cost_minor_units: completed.reduce((sum, r) => sum + (r.actual_cost_minor_units ?? 0), 0),
        currency: "CNY",
      },
      failed_runs: failed.slice(0, 5),
      degraded: db.providers
        .filter((p) => p.health_status !== "healthy")
        .map((p) => ({
          provider_id: p.provider_id,
          provider_name: p.name,
          reason: p.health_status === "unavailable" ? "连续调用失败，已切换备用路由。" : "响应缓慢，成功率下降。",
        })),
      capability_primaries: db.routes.map((route) => {
        const model = db.models.find((m) => m.model_id === route.primary_model_id);
        return { capability: route.capability, model_id: route.primary_model_id, business_name: model?.business_name ?? "", provider_name: model?.provider_name ?? "" };
      }),
    });
  }),

  http.get(api("/admin/model-gateway/providers"), async () => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    return ok(getDb().providers);
  }),

  http.post(api("/admin/model-gateway/providers"), async ({ request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const body = (await request.json()) as Record<string, unknown> & { credential_value?: string };
    if (!body.name || !body.base_url) {
      return fail(422, "VALIDATION_FAILED", "服务名称与接入地址不能为空。", { details: { field_errors: { ...(body.name ? {} : { name: "名称不能为空" }), ...(body.base_url ? {} : { base_url: "接入地址不能为空" }) } } });
    }
    const provider: Provider = {
      provider_id: nextId(db, "prov"),
      name: String(body.name),
      provider_type: (body.provider_type as Provider["provider_type"]) ?? "text",
      base_url: String(body.base_url),
      auth_method: String(body.auth_method ?? "api_key"),
      enabled: body.enabled !== false,
      environment: (body.environment as Provider["environment"]) ?? "production",
      health_status: "unknown",
      credential_status: body.credential_value ? "configured" : "missing",
      // 密钥只写不读：响应只返回掩码
      credential_mask: body.credential_value ? maskCredential(String(body.credential_value)) : null,
      credential_updated_at: body.credential_value ? minutesAgo(0) : null,
      timeout_seconds: Number(body.timeout_seconds ?? 120),
      retry_limit: Number(body.retry_limit ?? 2),
      concurrency_limit: Number(body.concurrency_limit ?? 4),
      rate_limit_per_minute: Number(body.rate_limit_per_minute ?? 60),
    };
    db.providers.push(provider);
    db.audit.unshift({ audit_id: nextId(db, "audit"), actor_name: db.session?.user.display_name ?? "管理员", actor_role: db.session?.user.role ?? "system_admin", action: "provider.create", object_type: "provider", object_id: provider.provider_id, summary: `新增模型服务「${provider.name}」`, occurred_at: minutesAgo(0), trace_id: nextId(db, "trace") });
    return ok(provider, { status: 201 });
  }),

  http.patch(api("/admin/model-gateway/providers/:providerId"), async ({ params, request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const provider = db.providers.find((p) => p.provider_id === String(params.providerId));
    if (!provider) return fail(404, "NOT_FOUND", "模型服务不存在。");
    const body = (await request.json()) as Record<string, unknown> & { credential_value?: string };
    if (typeof body.name === "string" && body.name.trim()) provider.name = body.name.trim();
    if (typeof body.base_url === "string" && body.base_url.trim()) provider.base_url = body.base_url.trim();
    if (typeof body.enabled === "boolean") provider.enabled = body.enabled;
    if (typeof body.timeout_seconds === "number") provider.timeout_seconds = body.timeout_seconds;
    if (typeof body.retry_limit === "number") provider.retry_limit = body.retry_limit;
    if (typeof body.concurrency_limit === "number") provider.concurrency_limit = body.concurrency_limit;
    if (typeof body.rate_limit_per_minute === "number") provider.rate_limit_per_minute = body.rate_limit_per_minute;
    if (typeof body.credential_value === "string" && body.credential_value.trim()) {
      provider.credential_status = "configured";
      provider.credential_mask = maskCredential(body.credential_value.trim());
      provider.credential_updated_at = minutesAgo(0);
    }
    db.audit.unshift({ audit_id: nextId(db, "audit"), actor_name: db.session?.user.display_name ?? "管理员", actor_role: db.session?.user.role ?? "system_admin", action: "provider.update", object_type: "provider", object_id: provider.provider_id, summary: `更新模型服务「${provider.name}」配置`, occurred_at: minutesAgo(0), trace_id: nextId(db, "trace") });
    return ok(provider);
  }),

  http.post(api("/admin/model-gateway/providers/:providerId/connection-tests"), async ({ params }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const provider = db.providers.find((p) => p.provider_id === String(params.providerId));
    if (!provider) return fail(404, "NOT_FOUND", "模型服务不存在。");
    const willFail = provider.health_status === "unavailable" || (db.flags.providerDegraded && provider.provider_id === "prov_video_1");
    const task = startTask({
      taskType: "provider_connection_test",
      projectId: "",
      durationMs: 3000,
      providerName: provider.name,
      failure: willFail ? { code: "CONNECTION_FAILED", message: `连接「${provider.name}」失败：上游服务超时。请检查接入地址与密钥有效性。`, retryable: true } : null,
      onComplete: () => {
        provider.health_status = "healthy";
      },
    });
    return ok(task, { status: 202 });
  }),

  http.get(api("/admin/model-gateway/models"), async () => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    return ok(getDb().models);
  }),

  http.patch(api("/admin/model-gateway/models/:modelId"), async ({ params, request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const model = db.models.find((m) => m.model_id === String(params.modelId));
    if (!model) return fail(404, "NOT_FOUND", "模型不存在。");
    const body = (await request.json()) as Record<string, unknown>;
    if (typeof body.business_name === "string" && body.business_name.trim()) model.business_name = body.business_name.trim();
    if (typeof body.enabled === "boolean") model.enabled = body.enabled;
    if (typeof body.recommended_scenarios === "string") model.recommended_scenarios = body.recommended_scenarios;
    if (body.pricing && typeof body.pricing === "object") model.pricing = body.pricing as typeof model.pricing;
    return ok(model);
  }),

  http.get(api("/admin/model-gateway/routes"), async () => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    return ok(getDb().routes);
  }),

  http.post(api("/admin/model-gateway/routes"), async ({ request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const body = (await request.json()) as Record<string, unknown>;
    const route = {
      route_policy_id: nextId(db, "route"),
      capability: String(body.capability ?? "text_generation"),
      mode: (body.mode as "quality" | "economy" | "speed" | "balanced" | "fixed") ?? "balanced",
      primary_model_id: String(body.primary_model_id ?? ""),
      fallback_model_ids: (body.fallback_model_ids as string[]) ?? [],
      allow_cross_provider_fallback: Boolean(body.allow_cross_provider_fallback),
      max_cost_minor_units: (body.max_cost_minor_units as number | null) ?? null,
      parameter_bounds: (body.parameter_bounds as Record<string, unknown>) ?? {},
      scope_organization_id: (body.scope_organization_id as string | null) ?? null,
      scope_project_id: (body.scope_project_id as string | null) ?? null,
      enabled: body.enabled !== false,
      updated_at: minutesAgo(0),
    };
    db.routes.push(route);
    return ok(route, { status: 201 });
  }),

  http.put(api("/admin/model-gateway/routes/:routePolicyId"), async ({ params, request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const index = db.routes.findIndex((r) => r.route_policy_id === String(params.routePolicyId));
    if (index === -1) return fail(404, "NOT_FOUND", "路由策略不存在。");
    const body = (await request.json()) as Record<string, unknown>;
    db.routes[index] = { ...db.routes[index], ...body, route_policy_id: db.routes[index].route_policy_id, updated_at: minutesAgo(0) } as (typeof db.routes)[number];
    return ok(db.routes[index]);
  }),

  http.post(api("/admin/model-gateway/routes/simulate"), async ({ request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const body = (await request.json()) as { capability?: string; mode?: string; primary_model_id?: string; fallback_model_ids?: string[] };
    const model = db.models.find((m) => m.model_id === body.primary_model_id) ?? db.models.find((m) => body.capability && m.capabilities.includes(body.capability));
    if (!model) {
      return fail(422, "VALIDATION_FAILED", "找不到满足该能力的可用模型。", { details: { field_errors: { primary_model_id: "请选择主模型" } } });
    }
    const conflicts: string[] = [];
    const existing = db.routes.filter((r) => r.capability === body.capability && r.enabled && !r.scope_project_id && !r.scope_organization_id);
    if (existing.length > 0 && !body.primary_model_id) {
      conflicts.push(`能力「${body.capability}」已存在全局策略，会被本策略覆盖`);
    }
    const fallbackChain = (body.fallback_model_ids ?? []).map((id) => {
      const fallback = db.models.find((m) => m.model_id === id);
      return { model_id: id, business_name: fallback?.business_name ?? id, provider_name: fallback?.provider_name ?? "" };
    });
    return ok({
      selected_model_id: model.model_id,
      selected_model_name: model.business_name,
      provider_name: model.provider_name ?? "",
      fallback_chain: fallbackChain,
      estimated_cost_note: model.pricing ? `按当前定价估算：${JSON.stringify(model.pricing)}` : null,
      conflicts,
    });
  }),

  http.get(api("/admin/model-gateway/budgets"), async () => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    return ok(getDb().budgets);
  }),

  http.put(api("/admin/model-gateway/budgets"), async ({ request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const body = (await request.json()) as Record<string, unknown> & { row_version?: number };
    if (Number(body.row_version) !== db.budgets.row_version) {
      return fail(409, "VERSION_CONFLICT", "预算配置已被其他管理员修改。", { details: { server_row_version: db.budgets.row_version } });
    }
    db.budgets = { ...db.budgets, ...body, row_version: db.budgets.row_version + 1 } as typeof db.budgets;
    db.audit.unshift({ audit_id: nextId(db, "audit"), actor_name: db.session?.user.display_name ?? "管理员", actor_role: db.session?.user.role ?? "system_admin", action: "budget.update", object_type: "budget", object_id: "platform", summary: "更新平台预算配置", occurred_at: minutesAgo(0), trace_id: nextId(db, "trace") });
    return ok(db.budgets);
  }),

  http.get(api("/admin/model-gateway/runs"), async ({ request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const url = new URL(request.url);
    const capability = url.searchParams.get("capability");
    const providerId = url.searchParams.get("provider_id");
    const status = url.searchParams.get("status");
    const projectId = url.searchParams.get("project_id");
    const fallbackOnly = url.searchParams.get("fallback_only") === "true";
    const pageSize = Number.parseInt(url.searchParams.get("page_size") ?? "30", 10);
    let items = [...db.modelRuns];
    if (capability) items = items.filter((r) => r.capability === capability);
    if (providerId) items = items.filter((r) => r.provider_id === providerId);
    if (status) items = items.filter((r) => r.status === status);
    if (projectId) items = items.filter((r) => r.project_id === projectId);
    if (fallbackOnly) items = items.filter((r) => r.is_fallback);
    items.sort((a, b) => b.created_at.localeCompare(a.created_at));
    const { page, nextCursor } = paginate(items, url.searchParams.get("cursor"), pageSize);
    return ok(page, { meta: { next_cursor: nextCursor } });
  }),

  http.get(api("/admin/model-gateway/runs/:modelRunId"), async ({ params }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const run = db.modelRuns.find((r) => r.model_run_id === String(params.modelRunId));
    if (!run) return fail(404, "NOT_FOUND", "运行记录不存在。");
    return ok({
      ...run,
      // 输入摘要脱敏：不含教师原文与密钥
      input_summary: "提示词长度 1,842 字；引用上游产物 2 项；参数 temperature=0.7。",
      parameters: { temperature: 0.7, candidate_count: 1 },
      provider_task_id: `up_${run.model_run_id}`,
      error: run.status === "failed" ? { code: "PROVIDER_TIMEOUT", message: "上游服务连续超时", retryable: true, action: null, details: {}, trace_id: `trace_${run.model_run_id}` } : null,
      fallback_chain: run.is_fallback ? [{ model_run_id: run.fallback_from_model_run_id ?? "", note: "主模型失败后切换" }] : [],
    });
  }),

  // ---------- 工作流 / 用户 / 组织 / 审计 ----------
  http.get(api("/admin/workflows"), async () => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    return ok(getDb().workflows);
  }),

  http.get(api("/admin/workflows/:workflowId"), async ({ params }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const detail = getDb().workflowDetails.get(String(params.workflowId));
    if (!detail) return fail(404, "NOT_FOUND", "工作流不存在。");
    return ok(detail);
  }),

  http.get(api("/admin/users"), async ({ request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const url = new URL(request.url);
    const role = url.searchParams.get("role");
    const status = url.searchParams.get("status");
    const keyword = url.searchParams.get("keyword")?.trim();
    let items = [...db.users];
    if (role) items = items.filter((u) => u.role === role);
    if (status) items = items.filter((u) => u.status === status);
    if (keyword) items = items.filter((u) => u.display_name.includes(keyword) || (u.email ?? "").includes(keyword));
    return ok(items);
  }),

  http.patch(api("/admin/users/:userId"), async ({ params, request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const user = db.users.find((u) => u.user_id === String(params.userId));
    if (!user) return fail(404, "NOT_FOUND", "用户不存在。");
    const body = (await request.json()) as { role?: string; status?: string; reason?: string };
    if (!body.reason?.trim()) {
      return fail(422, "VALIDATION_FAILED", "调整用户角色或状态必须填写原因（将进入审计记录）。", { details: { field_errors: { reason: "原因不能为空" } } });
    }
    if (body.role) user.role = body.role as typeof user.role;
    if (body.status) user.status = body.status as typeof user.status;
    db.audit.unshift({ audit_id: nextId(db, "audit"), actor_name: db.session?.user.display_name ?? "管理员", actor_role: db.session?.user.role ?? "system_admin", action: "user.update", object_type: "user", object_id: user.user_id, summary: `调整用户「${user.display_name}」：${body.reason}`, occurred_at: minutesAgo(0), trace_id: nextId(db, "trace") });
    return ok(user);
  }),

  http.get(api("/admin/organizations"), async () => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    return ok(getDb().organizations);
  }),

  http.get(api("/admin/audit"), async ({ request }) => {
    const unauth = adminGuard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const url = new URL(request.url);
    const action = url.searchParams.get("action");
    const objectType = url.searchParams.get("object_type");
    const keyword = url.searchParams.get("keyword")?.trim();
    const pageSize = Number.parseInt(url.searchParams.get("page_size") ?? "30", 10);
    let items = [...db.audit];
    if (action) items = items.filter((entry) => entry.action.startsWith(action));
    if (objectType) items = items.filter((entry) => entry.object_type === objectType);
    if (keyword) items = items.filter((entry) => (entry.summary ?? "").includes(keyword) || entry.actor_name.includes(keyword));
    const { page, nextCursor } = paginate(items, url.searchParams.get("cursor"), pageSize);
    return ok(page, { meta: { next_cursor: nextCursor } });
  }),
];
