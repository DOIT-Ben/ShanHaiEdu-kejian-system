export type ApiMode = "mock" | "real";

export function resolveApiMode(value: string | undefined, production: boolean): ApiMode {
  if (production) {
    if (value !== undefined && value !== "real") {
      throw new Error("生产构建只允许 VITE_API_MODE=real");
    }
    return "real";
  }
  if (value === undefined || value === "mock") return "mock";
  if (value === "real") return "real";
  throw new Error("VITE_API_MODE 只能是 mock 或 real");
}

export const apiConfig = {
  mode: resolveApiMode(import.meta.env.VITE_API_MODE, import.meta.env.PROD),
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api/v2",
  releaseVersion: import.meta.env.VITE_RELEASE_VERSION ?? "local",
} as const;
