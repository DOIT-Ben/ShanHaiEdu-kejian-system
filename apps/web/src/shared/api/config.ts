export const apiConfig = {
  mode: import.meta.env.VITE_API_MODE ?? (import.meta.env.PROD ? "real" : "mock"),
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api/v2",
  releaseVersion: import.meta.env.VITE_RELEASE_VERSION ?? "local",
} as const;
