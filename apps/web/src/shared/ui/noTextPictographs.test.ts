import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const sourceRoot = resolve(__dirname, "../..");
const forbiddenPictograph = /[\u{1f000}-\u{1faff}\u{2190}-\u{21ff}\u{2600}-\u{27ff}]/u;
const forbiddenJoiner = /\uFE0F|\u200D/u;
const forbiddenDecorativeIcon = /\b(?:Sparkles|WandSparkles)\b/;

describe("用户可见文本符号", () => {
  it("运行时源码不使用 emoji 或 Unicode 图形字符充当图标", () => {
    const offenders = readdirSync(sourceRoot, { recursive: true, withFileTypes: true })
      .filter(
        (entry) =>
          entry.isFile() &&
          /\.(?:ts|tsx)$/.test(entry.name) &&
          !/\.(?:test|stories)\.(?:ts|tsx)$/.test(entry.name),
      )
      .map((entry) => resolve(entry.parentPath, entry.name))
      .filter((file) => {
        const source = readFileSync(file, "utf8");
        return (
          forbiddenPictograph.test(source) ||
          forbiddenJoiner.test(source) ||
          forbiddenDecorativeIcon.test(source)
        );
      })
      .map((file) => file.slice(sourceRoot.length + 1));

    expect(offenders).toEqual([]);
  });
});
