import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const appRoot = existsSync(join(process.cwd(), "src/shared/styles/tokens.css"))
  ? process.cwd()
  : join(process.cwd(), "apps/web");
const tokens = readFileSync(join(appRoot, "src/shared/styles/tokens.css"), "utf8").replace(
  /\r\n/g,
  "\n",
);

function contrastRatio(foreground: string, background: string) {
  const luminance = (hex: string) => {
    const channels = hex
      .slice(1)
      .match(/.{2}/g)
      ?.map((channel) => Number.parseInt(channel, 16) / 255);
    if (!channels) throw new Error(`无效颜色：${hex}`);
    const [red, green, blue] = channels.map((channel) =>
      channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
    );
    if (red === undefined || green === undefined || blue === undefined) {
      throw new Error(`颜色必须包含 RGB 三个通道：${hex}`);
    }
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
  };
  const light = Math.max(luminance(foreground), luminance(background));
  const dark = Math.min(luminance(foreground), luminance(background));
  return (light + 0.05) / (dark + 0.05);
}

describe("全局三模式视觉令牌", () => {
  it.each([
    ["护眼", ':root,\n:root[data-theme="eye-care"]'],
    ["白天", ':root[data-theme="day"]'],
    ["黑夜", ':root[data-theme="night"]'],
  ])("定义%s模式", (_, selector) => {
    expect(tokens).toContain(selector);
  });

  it("护眼模式使用低饱和暖绿色", () => {
    expect(tokens).toContain("--sh-surface-canvas: #f3f7ee");
    expect(tokens).toContain("--sh-brand-500: #7f9d72");
  });

  it("白天模式使用纯白主背景", () => {
    expect(tokens).toMatch(/:root\[data-theme="day"\][\s\S]*--sh-surface-canvas: #ffffff/);
  });

  it("黑夜模式使用暗灰而不是纯黑", () => {
    const night = tokens.match(/:root\[data-theme="night"\]\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";
    expect(night).toContain("--sh-surface-canvas: #272b29");
    expect(night).not.toMatch(/#000(?:000)?\b/i);
  });

  it.each([
    ["护眼", "#465344", "#f3f7ee"],
    ["白天", "#353a3e", "#ffffff"],
    ["黑夜", "#dde1da", "#272b29"],
  ])("%s模式正文满足 AA", (_, foreground, background) => {
    expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(4.5);
  });

  it.each([
    ["护眼", "#526c49", "#e8efe2"],
    ["白天", "#795c46", "#f6f7f8"],
    ["黑夜", "#afc0a9", "#303532"],
  ])("%s模式操作文字在基础表面满足 AA", (_, foreground, background) => {
    expect(contrastRatio(foreground, background)).toBeGreaterThanOrEqual(4.5);
  });

  it("工作台分组标题使用满足 AA 的次级文字令牌", () => {
    const navigation = readFileSync(
      join(appRoot, "src/features/workbench/components/ProjectStepNavigation.tsx"),
      "utf8",
    );
    expect(contrastRatio("#596657", "#eaf1e5")).toBeGreaterThanOrEqual(4.5);
    expect(navigation).toMatch(
      /<p className="[^"]*text-\[var\(--sh-ink-muted\)\][^"]*">\s*\{group\.group\}/,
    );
  });

  it("锁定结构尺寸、作品纸张与动效节奏", () => {
    expect(tokens).toContain("--sh-artifact-paper: #ffffff");
    expect(tokens).toContain("--sh-artifact-on-dark: #ffffff");
    expect(tokens).toMatch(/--sh-overlay-scrim: rgb\([^)]+\)/);
    expect(tokens).toContain("--sh-radius-lg: 16px");
    expect(tokens).toContain("--sh-topbar-height: 60px");
    expect(tokens).toContain("--sh-project-sidebar-width: 240px");
    expect(tokens).toContain("--sh-duration-generation: 650ms");
  });

  it("主题相关组件不再硬编码摩卡阴影", () => {
    const files = [
      "src/layouts/GlobalAppShell.tsx",
      "src/shared/ui/Button.tsx",
      "src/shared/ui/Select.tsx",
      "src/features/creation-studio/CreationComposer.tsx",
      "src/pages/projects/NewProjectPage.tsx",
      "src/pages/creation/CreationStudioPage.tsx",
    ];
    for (const file of files) {
      expect(readFileSync(join(appRoot, file), "utf8"), file).not.toMatch(/shadow-\[[^\]]*rgb\(/);
    }
  });
});
