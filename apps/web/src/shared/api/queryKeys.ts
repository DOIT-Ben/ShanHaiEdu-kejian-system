/**
 * TanStack Query Key 目录。
 * SSE 事件按资源类型映射到这里的 key 前缀做精准失效。
 */
export const qk = {
  session: ["session"] as const,
  home: ["home"] as const,
  projects: {
    all: ["projects"] as const,
    list: () => ["projects", "list"] as const,
    detail: (projectId: string) => ["projects", projectId] as const,
    workflow: (projectId: string) => ["projects", projectId, "workflow"] as const,
    material: (projectId: string) => ["projects", projectId, "material"] as const,
    division: (projectId: string) => ["projects", projectId, "division"] as const,
    lessons: (projectId: string) => ["projects", projectId, "lessons"] as const,
    assets: (projectId: string, filters?: Record<string, string>) =>
      ["projects", projectId, "assets", filters ?? {}] as const,
    delivery: (projectId: string) => ["projects", projectId, "delivery"] as const,
  },
  lessons: {
    detail: (lessonId: string) => ["lessons", lessonId] as const,
    nodeRuns: (lessonId: string) => ["lessons", lessonId, "node-runs"] as const,
    introOptions: (lessonId: string) => ["lessons", lessonId, "intro-options"] as const,
    introSelection: (lessonId: string) => ["lessons", lessonId, "intro-selection"] as const,
    pptPages: (lessonId: string) => ["lessons", lessonId, "ppt-pages"] as const,
    pptStyleContract: (lessonId: string) => ["lessons", lessonId, "ppt-style-contract"] as const,
    videoProject: (lessonId: string) => ["lessons", lessonId, "video-project"] as const,
  },
  nodeRuns: {
    detail: (nodeRunId: string) => ["node-runs", nodeRunId] as const,
    promptPreview: (nodeRunId: string) => ["node-runs", nodeRunId, "prompt-preview"] as const,
    results: (nodeRunId: string, itemKey?: string) =>
      ["node-runs", nodeRunId, "results", itemKey ?? "all"] as const,
  },
  artifacts: {
    version: (versionId: string) => ["artifact-versions", versionId] as const,
  },
  pptPages: {
    detail: (pageId: string) => ["ppt-pages", pageId] as const,
  },
  videoProjects: {
    shots: (videoProjectId: string) => ["video-projects", videoProjectId, "shots"] as const,
  },
  jobs: {
    all: ["generation-jobs"] as const,
    list: (filters?: Record<string, string | boolean>) =>
      ["generation-jobs", "list", filters ?? {}] as const,
    detail: (jobId: string) => ["generation-jobs", jobId] as const,
  },
  batches: {
    all: ["creation-batches"] as const,
    list: (studioType?: string) => ["creation-batches", "list", studioType ?? "all"] as const,
    detail: (batchId: string) => ["creation-batches", batchId] as const,
    results: (batchId: string, itemKey?: string) =>
      ["creation-batches", batchId, "results", itemKey ?? "all"] as const,
  },
  packages: {
    detail: (packageId: string) => ["creation-packages", packageId] as const,
  },
  admin: {
    contentPackages: ["admin", "content-packages"] as const,
    contentPackage: (id: string) => ["admin", "content-packages", id] as const,
    workflows: ["admin", "workflows"] as const,
    workflow: (id: string) => ["admin", "workflows", id] as const,
    modelOverview: ["admin", "model-overview"] as const,
    providers: ["admin", "providers"] as const,
    models: ["admin", "models"] as const,
    usage: ["admin", "usage"] as const,
    modelRuns: (filters?: Record<string, string>) =>
      ["admin", "model-runs", filters ?? {}] as const,
    users: ["admin", "users"] as const,
    audit: (filters?: Record<string, string>) => ["admin", "audit", filters ?? {}] as const,
  },
} as const;
