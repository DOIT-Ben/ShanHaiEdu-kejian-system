import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { AppProviders } from "./app/providers";
import { router } from "./app/router";
import { env } from "./shared/config/env";
import "./shared/styles/globals.css";

/**
 * 启动流程：
 * - mock 模式：动态加载 MSW（构建时 stripMockWorker 保证生产包不含 mock 代码），
 *   并在 window 上挂调试控制器供场景切换徽标使用；
 * - real 模式：直接渲染，所有请求走后端网关。
 */
async function bootstrap(): Promise<void> {
  // 用编译期常量做守卫：real 构建中该分支被静态消除，MSW 代码不会进入产物
  if (import.meta.env.VITE_API_MODE === "mock" && env.apiMode === "mock") {
    const { startMockWorker, setActiveScenario } = await import("./mocks/browser");
    const { SCENARIOS } = await import("./mocks/scenarios");
    const scenarioId = await startMockWorker();
    window.__SHANHAI_MOCK__ = {
      scenarioId,
      scenarios: SCENARIOS.map((scenario) => ({
        id: scenario.id,
        group: scenario.group,
        description: scenario.description,
      })),
      setScenario: setActiveScenario,
    };
  }

  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </StrictMode>,
  );
}

void bootstrap();
