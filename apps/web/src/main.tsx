import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "@/app/App";
import { AppProviders } from "@/app/providers/AppProviders";
import { apiConfig } from "@/shared/api/config";
import "@/shared/styles/index.css";

async function enableMocking() {
  if (!import.meta.env.DEV || apiConfig.mode !== "mock") {
    return;
  }

  const { startContractMocking } = await import("@/shared/api/mocks/browser");
  await startContractMocking();
}

async function enableRuntimeContractTest() {
  if (
    !import.meta.env.DEV ||
    apiConfig.mode !== "real" ||
    import.meta.env.VITE_RUNTIME_CONTRACT_TEST !== "1"
  ) {
    return;
  }
  const { enableRuntimeContractTestCsrf } =
    await import("@/shared/api/runtimeContractTestBootstrap.development");
  enableRuntimeContractTestCsrf();
}

await enableMocking();
await enableRuntimeContractTest();

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("页面根节点不存在");
}

createRoot(rootElement).render(
  <StrictMode>
    <AppProviders>
      <App />
    </AppProviders>
  </StrictMode>,
);
