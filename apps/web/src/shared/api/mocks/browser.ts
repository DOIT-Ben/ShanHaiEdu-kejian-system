import { setupWorker } from "msw/browser";
import { configureCsrfTokenProvider } from "@/shared/api/client";
import { apiConfig } from "@/shared/api/config";
import { handlers } from "@/shared/api/mocks/handlers";

const worker = setupWorker(...handlers);

function isRuntimeApiRequest(request: Request) {
  const requestUrl = new URL(request.url);
  const apiUrl = new URL(apiConfig.baseUrl, globalThis.location.origin);
  const apiPath = apiUrl.pathname.replace(/\/$/, "");
  return requestUrl.origin === apiUrl.origin && requestUrl.pathname.startsWith(`${apiPath}/`);
}

export async function startContractMocking() {
  configureCsrfTokenProvider(() => "development-contract-csrf");
  await worker.start({
    onUnhandledRequest(request, print) {
      if (!isRuntimeApiRequest(request)) return;
      print.error();
      throw new Error(
        `未声明的 Runtime API 请求：${request.method} ${new URL(request.url).pathname}`,
      );
    },
  });
}
