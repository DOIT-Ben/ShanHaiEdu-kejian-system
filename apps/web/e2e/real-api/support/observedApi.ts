import { expect, type Page } from "@playwright/test";

export interface ExpectedApiRequest {
  method: string;
  path: string;
}

export interface ObservedApiRequest {
  method: string;
  path: string;
}

export type ObservedApiRequests = () => readonly ObservedApiRequest[];

export function observeApiRequests(page: Page): ObservedApiRequests {
  const observed: ObservedApiRequest[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/v2/")) return;
    observed.push({
      method: request.method().toUpperCase(),
      path: url.pathname.slice("/api/v2".length) || "/",
    });
  });
  return () => observed.map((request) => ({ ...request }));
}

function pathMatchesTemplate(actualPath: string, pathTemplate: string): boolean {
  const templateSegments = pathTemplate.split("/");
  const actualSegments = actualPath.split("/");
  if (templateSegments.length !== actualSegments.length) return false;
  return templateSegments.every(
    (segment, index) =>
      (/^\{[^{}]+\}$/.test(segment) && Boolean(actualSegments[index])) ||
      segment === actualSegments[index],
  );
}

export function expectObservedApi(
  getObserved: ObservedApiRequests,
  expected: ExpectedApiRequest[],
): void {
  for (const request of expected) {
    expect(
      getObserved().some(
        (observed) =>
          observed.method === request.method.toUpperCase() &&
          pathMatchesTemplate(observed.path, request.path),
      ),
    ).toBe(true);
  }
}
