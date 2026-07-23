import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(({ command }) => {
  const realApiProxyTarget = process.env.VITE_REAL_API_PROXY_TARGET?.trim();

  return {
    plugins: [react(), tailwindcss()],
    publicDir: command === "build" ? false : "public",
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    optimizeDeps: {
      entries: ["index.html"],
    },
    server: {
      port: 5173,
      proxy: realApiProxyTarget
        ? {
            "/api": {
              changeOrigin: false,
              target: realApiProxyTarget,
            },
          }
        : undefined,
    },
    preview: {
      port: 4173,
    },
  };
});
