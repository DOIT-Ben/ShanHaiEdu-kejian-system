import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";
import { existsSync, rmSync } from "node:fs";
import { resolve } from "node:path";

/**
 * 生产构建不允许携带 MSW：
 * - VITE_API_MODE 由 mode 推导，业务代码只读 env.apiMode。
 * - public/mockServiceWorker.js 仅在 mock 模式保留，其余构建产物中删除。
 */
function stripMockWorker(mode: string): Plugin {
  return {
    name: "shanhai:strip-mock-worker",
    apply: "build",
    closeBundle() {
      if (mode === "mock") return;
      const worker = resolve(__dirname, "dist/mockServiceWorker.js");
      if (existsSync(worker)) rmSync(worker);
    },
  };
}

export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, __dirname, "VITE_");
  const apiMode = mode === "mock" ? "mock" : (fileEnv.VITE_API_MODE ?? "real");
  if (mode === "production" && apiMode === "mock") {
    throw new Error("生产构建不允许 VITE_API_MODE=mock");
  }

  return {
    plugins: [react(), tailwindcss(), stripMockWorker(mode)],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    define: {
      "import.meta.env.VITE_API_MODE": JSON.stringify(apiMode),
    },
    build: {
      sourcemap: true,
      chunkSizeWarningLimit: 900,
    },
    server: {
      port: 5173,
      proxy:
        apiMode === "real"
          ? {
              "/api/v2": {
                target: fileEnv.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
                changeOrigin: true,
              },
            }
          : undefined,
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: false,
      // Node fetch/Request 需要绝对 URL（MSW handler 匹配任意 origin）
      env: {
        VITE_API_BASE_URL: "http://localhost/api/v2",
      },
      include: ["src/**/*.test.{ts,tsx}"],
      exclude: ["e2e/**", "node_modules/**"],
      coverage: {
        provider: "v8" as const,
        reporter: ["text", "html"],
        include: ["src/shared/**", "src/features/**", "src/entities/**"],
      },
    },
  };
});
