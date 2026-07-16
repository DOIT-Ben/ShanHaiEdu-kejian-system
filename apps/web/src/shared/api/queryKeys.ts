/**
 * 统一 Query Key 工厂。
 * Mutation 成功后按域精确失效，禁止无差别清空全部缓存；
 * SSE 事件只触发这些 Key 的失效，不直接写入缓存对象。
 */
export const qk = {
  session: ["session"] as const,
  homeOverview: ["home", "overview"] as const,

  projects: {
    root: ["projects"] as const,
    list: (filters?: Record<string, unknown>) => ["projects", "list", filters ?? {}] as const,
    detail: (projectId: string) => ["projects", "detail", projectId] as const,
    evidence: (projectId: string) => ["projects", projectId, "textbook-evidence"] as const,
    division: (projectId: string) => ["projects", projectId, "lesson-division"] as const,
    divisionVersions: (projectId: string) =>
      ["projects", projectId, "lesson-division", "versions"] as const,
    lessons: (projectId: string) => ["projects", projectId, "lessons"] as const,
    assets: (projectId: string, filters?: Record<string, unknown>) =>
      ["projects", projectId, "assets", filters ?? {}] as const,
    assetsRoot: (projectId: string) => ["projects", projectId, "assets"] as const,
    tasks: (projectId: string, filters?: Record<string, unknown>) =>
      ["projects", projectId, "tasks", filters ?? {}] as const,
    tasksRoot: (projectId: string) => ["projects", projectId, "tasks"] as const,
    delivery: (projectId: string, lessonId?: string) =>
      ["projects", projectId, "delivery", lessonId ?? "all"] as const,
    deliveryRoot: (projectId: string) => ["projects", projectId, "delivery"] as const,
  },

  lessons: {
    detail: (lessonId: string) => ["lessons", lessonId] as const,
    workspace: (lessonId: string) => ["lessons", lessonId, "workspace"] as const,
    node: (lessonId: string, nodeKey: string) => ["lessons", lessonId, "nodes", nodeKey] as const,
    nodesRoot: (lessonId: string) => ["lessons", lessonId, "nodes"] as const,
    modelOptions: (lessonId: string, nodeKey: string) =>
      ["lessons", lessonId, "nodes", nodeKey, "model-options"] as const,
  },

  tasks: {
    mine: ["tasks", "mine"] as const,
    detail: (taskId: string) => ["tasks", "detail", taskId] as const,
  },

  assets: {
    detail: (assetId: string) => ["assets", assetId] as const,
  },

  artifacts: {
    version: (versionId: string) => ["artifact-versions", versionId] as const,
  },

  admin: {
    templates: (filters?: Record<string, unknown>) => ["admin", "templates", filters ?? {}] as const,
    templatesRoot: ["admin", "templates"] as const,
    templateDetail: (templateId: string) => ["admin", "templates", "detail", templateId] as const,
    gatewayOverview: ["admin", "gateway", "overview"] as const,
    providers: ["admin", "gateway", "providers"] as const,
    models: ["admin", "gateway", "models"] as const,
    routes: ["admin", "gateway", "routes"] as const,
    budgets: ["admin", "gateway", "budgets"] as const,
    modelRuns: (filters?: Record<string, unknown>) =>
      ["admin", "gateway", "runs", filters ?? {}] as const,
    modelRunsRoot: ["admin", "gateway", "runs"] as const,
    modelRunDetail: (modelRunId: string) => ["admin", "gateway", "runs", "detail", modelRunId] as const,
    workflows: ["admin", "workflows"] as const,
    workflowDetail: (workflowId: string) => ["admin", "workflows", workflowId] as const,
    users: (filters?: Record<string, unknown>) => ["admin", "users", filters ?? {}] as const,
    usersRoot: ["admin", "users"] as const,
    organizations: ["admin", "organizations"] as const,
    audit: (filters?: Record<string, unknown>) => ["admin", "audit", filters ?? {}] as const,
  },
} as const;
