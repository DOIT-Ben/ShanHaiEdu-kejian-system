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

await enableMocking();

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
