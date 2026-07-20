import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const appRoot = existsSync(join(process.cwd(), "src/shared/styles/tokens.css"))
  ? process.cwd()
  : join(process.cwd(), "apps/web");
const tokens = readFileSync(join(appRoot, "src/shared/styles/tokens.css"), "utf8").replace(
  /\r\n/g,
  "\n",
);

function cssBlock(selector: string) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return tokens.match(new RegExp(`${escaped}\\s*\\{([\\s\\S]*?)\\n\\}`))?.[1] ?? "";
}

function tokenValue(block: string, name: string) {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const value = block.match(new RegExp(`${escaped}:\\s*([^;]+);`))?.[1]?.trim();
  if (!value) throw new Error(`缺少令牌 ${name}`);
  return value;
}

function inheritedTokenValue(block: string, name: string) {
  const direct = block
    .match(new RegExp(`${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}:\\s*([^;]+);`))?.[1]
    ?.trim();
  return direct ?? tokenValue(cssBlock(":root"), name);
}

function oklchToLuminance(value: string) {
  const match = /oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)/.exec(value);
  if (!match) throw new Error(`无效 OKLCH 颜色：${value}`);
  const lightness = Number(match[1]);
  const chroma = Number(match[2]);
  const hue = (Number(match[3]) * Math.PI) / 180;
  const a = chroma * Math.cos(hue);
  const b = chroma * Math.sin(hue);
  const lRoot = lightness + 0.3963377774 * a + 0.2158037573 * b;
  const mRoot = lightness - 0.1055613458 * a - 0.0638541728 * b;
  const sRoot = lightness - 0.0894841775 * a - 1.291485548 * b;
  const l = lRoot ** 3;
  const m = mRoot ** 3;
  const s = sRoot ** 3;
  const clamp = (channel: number) => Math.min(1, Math.max(0, channel));
  const red = clamp(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s);
  const green = clamp(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s);
  const blue = clamp(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s);
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrastRatio(foreground: string, background: string) {
  const foregroundLuminance = oklchToLuminance(foreground);
  const backgroundLuminance = oklchToLuminance(background);
  const light = Math.max(foregroundLuminance, backgroundLuminance);
  const dark = Math.min(foregroundLuminance, backgroundLuminance);
  return (light + 0.05) / (dark + 0.05);
}

const themeBlocks = [
  ["护眼", cssBlock(":root")],
  ["白天", cssBlock(':root[data-theme="day"]')],
  ["黑夜", cssBlock(':root[data-theme="night"]')],
] as const;

describe("全局三模式视觉令牌", () => {
  it("保留护眼默认值并为白天和黑夜只覆盖基础色槽", () => {
    expect(tokens).toContain(':root[data-theme="eye-care"]');
    expect(tokens).toContain(':root[data-theme="day"]');
    expect(tokens).toContain(':root[data-theme="night"]');
    expect(cssBlock(':root[data-theme="day"]')).not.toContain("--sh-surface-canvas:");
    expect(cssBlock(':root[data-theme="night"]')).not.toContain("--sh-action-primary:");
  });

  it("基础色槽全部使用 OKLCH", () => {
    const declarations = [...tokens.matchAll(/--sh-color-[\w-]+:\s*([^;]+);/g)].map(
      (match) => match[1]?.trim() ?? "",
    );
    expect(declarations.length).toBeGreaterThan(50);
    expect(declarations.every((value) => value.startsWith("oklch("))).toBe(true);
  });

  it("除浏览器主题色兼容值外不保留 Hex 或 RGB 设计令牌", () => {
    const offenders = tokens
      .split("\n")
      .filter((line) => /^\s*--sh-/.test(line))
      .filter((line) => !line.includes("--sh-theme-color:"))
      .filter((line) => /#[\da-f]{3,8}\b|rgba?\(/i.test(line));
    expect(offenders).toEqual([]);
    expect(tokens.match(/--sh-theme-color:\s*#[\da-f]{6}/gi)).toHaveLength(3);
  });

  it("语义层只引用基础色槽", () => {
    for (const name of [
      "--sh-brand-500",
      "--sh-ink-default",
      "--sh-surface-canvas",
      "--sh-success",
      "--sh-warning",
      "--sh-danger",
      "--sh-info",
    ]) {
      expect(tokens).toMatch(new RegExp(`${name}:\\s*var\\(--sh-color-`));
    }
  });

  it("普通控件、卡片和弹窗使用 6px/8px 两档圆角", () => {
    expect(tokens).toContain("--sh-radius-control: 6px");
    expect(tokens).toContain("--sh-radius-card: 8px");
    expect(tokens).toContain("--sh-radius-dialog: 8px");
    expect(tokens).not.toMatch(/--sh-radius-(?:sm|md|lg):\s*(?:10|12|16|20|22)px/);
  });

  it("删除 Hero、工作区和行动渐变，提供纯色行动令牌", () => {
    expect(tokens).not.toMatch(/--sh-(?:hero|workspace|action)-gradient/);
    expect(tokens).not.toMatch(/(?:linear|radial)-gradient\(/);
    expect(tokens).toContain("--sh-action-primary: var(--sh-color-action-primary)");
    expect(tokens).toContain("--sh-action-hover: var(--sh-color-action-hover)");
    expect(tokens).toContain("--sh-action-active: var(--sh-color-action-active)");

    const files = readdirSync(resolve(appRoot, "src"), { recursive: true, withFileTypes: true })
      .filter(
        (entry) =>
          entry.isFile() &&
          /\.(?:css|ts|tsx)$/.test(entry.name) &&
          !/\.(?:test|stories)\.(?:ts|tsx)$/.test(entry.name),
      )
      .map((entry) => resolve(entry.parentPath, entry.name));
    const offenders = files.filter((file) =>
      /--sh-(?:hero|workspace|action)-gradient/.test(readFileSync(file, "utf8")),
    );
    expect(offenders).toEqual([]);
  });

  it("补齐信息状态和完整品牌色阶", () => {
    for (const token of [
      "--sh-info",
      "--sh-info-soft",
      "--sh-info-strong",
      "--sh-brand-200",
      "--sh-brand-400",
      "--sh-brand-800",
    ]) {
      expect(tokens).toContain(`${token}: var(--sh-color-`);
    }
  });

  it.each(themeBlocks)("%s模式正文满足 WCAG AA", (_, block) => {
    expect(
      contrastRatio(
        tokenValue(block, "--sh-color-ink-default"),
        tokenValue(block, "--sh-color-surface-canvas"),
      ),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it.each(themeBlocks)("%s模式主行动默认和悬停态满足 WCAG AA", (_, block) => {
    const foreground = inheritedTokenValue(block, "--sh-color-action-foreground");
    expect(
      contrastRatio(foreground, inheritedTokenValue(block, "--sh-color-action-primary")),
    ).toBeGreaterThanOrEqual(4.5);
    expect(
      contrastRatio(foreground, inheritedTokenValue(block, "--sh-color-action-hover")),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("按钮组件消费纯色组件令牌", () => {
    for (const file of ["src/shared/ui/Button.tsx", "src/shared/ui/IconButton.tsx"]) {
      const source = readFileSync(join(appRoot, file), "utf8");
      expect(source).toContain("var(--sh-action-primary)");
      expect(source).toContain("var(--sh-action-hover)");
      expect(source).not.toContain("gradient");
    }
  });

  it("作品颜色固定为 OKLCH 并提供次级文字语义", () => {
    expect(tokens).toContain("--sh-artifact-paper: oklch(1 0 0)");
    expect(tokens).toContain("--sh-artifact-muted: var(--sh-art-navy-muted)");
    expect(
      contrastRatio(
        tokenValue(tokens, "--sh-art-green"),
        tokenValue(tokens, "--sh-artifact-paper"),
      ),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("字体角色由令牌定义，展示字体不覆盖工作台界面字体", () => {
    expect(tokens).toContain("--sh-font-interface:");
    expect(tokens).toContain("--sh-font-display:");
    const styles = readFileSync(join(appRoot, "src/shared/styles/index.css"), "utf8");
    expect(styles).toContain("font-family: var(--sh-font-interface)");
    expect(styles).toContain(".sh-display-type");
  });

  it("减少动态偏好同时关闭生成动画时长", () => {
    expect(tokens).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*--sh-duration-generation: 0ms/,
    );
  });
});
