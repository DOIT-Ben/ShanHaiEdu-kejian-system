import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "@/shared/styles/globals.css";

/**
 * 应用入口。
 * mock 分支使用编译期常量守卫：生产构建（VITE_API_MODE=real）中
 * 该分支为死代码，MSW 与全部 mock 模块不会进入产物（发布检查脚本二次校验）。
 */
async function bootstrap(): Promise<void> {
  if (import.meta.env.VITE_API_MODE === "mock") {
    const { startMockWorker } = await import("@/mocks/browser");
    await startMockWorker();
  }
  const container = document.getElementById("root");
  if (!container) throw new Error("找不到 #root 容器");
  createRoot(container).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void bootstrap();
