import { configureCsrfTokenProvider } from "@/shared/api/client";

export const RUNTIME_CONTRACT_TEST_CSRF_KEY = "shanhaiedu.runtime-contract-test.csrf";

/**
 * Development-only browser gate used by the deterministic Runtime Playwright
 * server. The token is supplied per browser context through sessionStorage;
 * no token value or fallback is compiled into the application.
 */
export function enableRuntimeContractTestCsrf() {
  const token = sessionStorage.getItem(RUNTIME_CONTRACT_TEST_CSRF_KEY)?.trim();
  if (token) configureCsrfTokenProvider(() => token);
}
