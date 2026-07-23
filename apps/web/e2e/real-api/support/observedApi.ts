import { expect, type Page } from "@playwright/test";

export interface ExpectedApiRequest {
  method: string;
  path: string;
}

export interface ObservedApiRequest {
  method: string;
  path: string;
}

export function observeApiRequests(page: Page): ObservedApiRequest[] {
  const observed: ObservedApiRequest[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/v2/")) return;
    observed.push({
      method: request.method().toUpperCase(),
      path: url.pathname.slice("/api/v2".length) || "/",
    });
  });
  return observed;
}

export function expectObservedApi(
  observed: ObservedApiRequest[],
  expected: ExpectedApiRequest[],
): void {
  for (const request of expected) {
    expect(observed).toContainEqual({
      method: request.method.toUpperCase(),
      path: request.path,
    });
  }
}
