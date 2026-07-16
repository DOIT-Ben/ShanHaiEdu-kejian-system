import { z } from "zod";

const envSchema = z.object({
  appName: z.string().min(1),
  apiBaseUrl: z.string().min(1),
  apiMode: z.enum(["mock", "real"]),
  buildVersion: z.string().min(1),
  eventStreamPath: z.string().min(1),
  sentryDsn: z.string().optional(),
});

export type AppEnv = z.infer<typeof envSchema>;

const parsed = envSchema.safeParse({
  appName: import.meta.env.VITE_APP_NAME ?? "山海教育课件工作台",
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api/v2",
  apiMode: import.meta.env.VITE_API_MODE ?? "real",
  buildVersion: import.meta.env.VITE_BUILD_VERSION ?? "local",
  eventStreamPath: import.meta.env.VITE_EVENT_STREAM_PATH ?? "/events",
  sentryDsn: import.meta.env.VITE_SENTRY_DSN || undefined,
});

if (!parsed.success) {
  throw new Error(`环境变量配置不合法：${parsed.error.message}`);
}

export const env: AppEnv = parsed.data;

// 生产构建禁止 Mock（vite.config 已在构建期拦截，这里做运行期兜底）。
if (import.meta.env.PROD && env.apiMode === "mock") {
  throw new Error("生产构建不允许启用 Mock 模式");
}
