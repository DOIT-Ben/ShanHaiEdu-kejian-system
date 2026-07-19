import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("全局样式可访问性", () => {
  it("不覆盖链接自身的颜色令牌", () => {
    const stylesheet = readFileSync(resolve(__dirname, "index.css"), "utf8");
    expect(stylesheet).not.toMatch(/a\s*\{[^}]*color:\s*inherit/s);
  });

  it("触屏设备把紧凑控件提升到 44px", () => {
    const stylesheet = readFileSync(resolve(__dirname, "index.css"), "utf8");
    expect(stylesheet).toMatch(
      /@media \(pointer: coarse\)[\s\S]*\.sh-control-compact[\s\S]*min-height: 2\.75rem/,
    );
  });

  it("保留 Tailwind 白色语义，不把真实白色劫持为主题表面", () => {
    const stylesheet = readFileSync(resolve(__dirname, "index.css"), "utf8");
    expect(stylesheet).not.toContain("--color-white: var(--sh-surface-elevated)");
    expect(stylesheet).not.toMatch(/\.text-white(?:\\\/[0-9]+)?\s*\{/);
  });

  it("界面表面不再使用含义模糊的纯 bg-white", () => {
    const sourceRoot = resolve(__dirname, "../..");
    const sourceFiles = readdirSync(sourceRoot, { recursive: true, withFileTypes: true })
      .filter(
        (entry) =>
          entry.isFile() &&
          /\.(?:ts|tsx)$/.test(entry.name) &&
          !/\.(?:test|stories)\.(?:ts|tsx)$/.test(entry.name),
      )
      .map((entry) => resolve(entry.parentPath, entry.name));
    const offenders = sourceFiles.filter((file) =>
      /(?:^|[\s:])bg-white(?=[\s"'`}])/.test(readFileSync(file, "utf8")),
    );
    expect(offenders).toEqual([]);
  });
});
