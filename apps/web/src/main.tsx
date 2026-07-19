import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "@/app/App";
import { AppProviders } from "@/app/providers/AppProviders";
import "@/shared/styles/index.css";

async function enableMocking() {
  if ((import.meta.env.VITE_API_MODE ?? "mock") !== "mock" || import.meta.env.PROD) {
    return;
  }

  const { worker } = await import("@/shared/api/mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass" });
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
