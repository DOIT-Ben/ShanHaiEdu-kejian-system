/**
 * 环境配置唯一入口。业务代码不得直接读 import.meta.env。
 * VITE_API_MODE 由 vite.config define 注入（mock 模式仅存在于 dev/test）。
 */
export interface AppEnv {
  appName: string;
  apiBaseUrl: string;
  apiMode: "mock" | "real";
  buildVersion: string;
}

export const env: AppEnv = {
  appName: import.meta.env.VITE_APP_NAME ?? "山海教育课件系统",
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api/v2",
  apiMode: import.meta.env.VITE_API_MODE === "mock" ? "mock" : "real",
  buildVersion: import.meta.env.VITE_BUILD_VERSION ?? "dev",
};
