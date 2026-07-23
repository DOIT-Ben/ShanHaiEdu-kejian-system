import { readdirSync, readFileSync } from "node:fs";
import { extname, join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const sourceRoot = resolve(__dirname, "..");
const forbiddenImports = [
  "@/app/MockApp",
  "@/shared/api/mockClient",
  "@/shared/auth/mockAuth",
  "@/shared/data/mockData",
  "@/shared/api/mocks/runtime",
];

function productionSources(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      if (relative(sourceRoot, path).replaceAll("\\", "/") === "shared/api/mocks") return [];
      return productionSources(path);
    }
    if (![".ts", ".tsx"].includes(extname(path))) return [];
    if (/\.(?:test|spec|stories)\.[^.]+$/.test(path)) return [];
    return [path];
  });
}

describe("production source boundaries", () => {
  it("所有用户路由只由 RuntimeApp 提供", () => {
    const appSource = readFileSync(resolve(sourceRoot, "app/App.tsx"), "utf8");

    expect(appSource).toContain('import("@/app/RuntimeApp")');
    expect(appSource).not.toContain("MockApp");
    expect(appSource).not.toContain("apiConfig.mode");
  });

  it("生产路由保留独立可用的创作中心", () => {
    const runtimeSource = readFileSync(resolve(sourceRoot, "app/RuntimeApp.tsx"), "utf8");

    expect(runtimeSource).toContain('import("@/pages/creation/CreationHomePage")');
    expect(runtimeSource).toContain('import("@/pages/creation/CreationStudioPage")');
    expect(runtimeSource).toContain('path="creation"');
    expect(runtimeSource).toContain('path="creation/:studioPath"');
    expect(runtimeSource).not.toContain("creationAvailable={false}");
    expect(runtimeSource).not.toMatch(
      /<Route element={<RuntimeUnavailablePage \/>} path="creation\/\*" \/>/,
    );
  });

  it("生产源不静态导入开发 Mock 真源", () => {
    const violations = productionSources(sourceRoot).flatMap((path) => {
      const source = readFileSync(path, "utf8");
      return forbiddenImports
        .filter((specifier) => source.includes(`from "${specifier}`))
        .map((specifier) => `${relative(sourceRoot, path)} -> ${specifier}`);
    });

    expect(violations).toEqual([]);
  });

  it("合同 handlers 不恢复浏览器状态机、假进度或已退出的 API", () => {
    const handlerSource = readFileSync(resolve(sourceRoot, "shared/api/mocks/handlers.ts"), "utf8");

    expect(handlerSource).not.toMatch(/localStorage|sessionStorage|setTimeout|setInterval/);
    expect(handlerSource).not.toMatch(/useMockRuntime|saveMockDraft|createMockTask/);
    expect(handlerSource).not.toContain("OPTIMISTIC_LOCK_CONFLICT");
    expect(handlerSource).toContain('"EDIT_CONFLICT"');
    expect(handlerSource).not.toContain("/intro-options");
    expect(handlerSource).not.toContain("/intro-selections");
    expect(handlerSource).not.toContain("/start`");
    expect(handlerSource).not.toContain("/creation-packages");
  });
});
