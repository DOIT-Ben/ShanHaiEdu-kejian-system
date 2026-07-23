import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import {
  DEFAULT_THEME,
  getThemeMode,
  setThemeMode,
  THEME_MODES,
  THEME_STORAGE_KEY,
} from "@/shared/theme/theme";

const appRoot = existsSync(join(process.cwd(), "index.html"))
  ? process.cwd()
  : join(process.cwd(), "apps/web");

describe("全局主题控制", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.dataset.theme = DEFAULT_THEME;
  });

  it("默认使用护眼模式", () => {
    document.documentElement.dataset.theme = "unknown";
    expect(getThemeMode()).toBe("eye-care");
  });

  it.each(["eye-care", "day", "night", "atelier"] as const)("切换并持久化 %s", (mode) => {
    setThemeMode(mode);
    expect(document.documentElement.dataset.theme).toBe(mode);
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe(mode);
    expect(document.documentElement.style.colorScheme).toBe(mode === "night" ? "dark" : "light");
  });

  it("首屏脚本与主题模块共享模式、默认值、存储键和主题色", () => {
    const bootstrap = readFileSync(join(appRoot, "index.html"), "utf8");
    const tokens = readFileSync(join(appRoot, "src/shared/styles/tokens.css"), "utf8");
    const themeColors = [...tokens.matchAll(/--sh-theme-color:\s*(#[0-9a-f]{6})/gi)].map(
      (match) => match[1],
    );

    expect(bootstrap).toContain(`const key = "${THEME_STORAGE_KEY}"`);
    expect(bootstrap).toContain(`let theme = "${DEFAULT_THEME}"`);
    expect(new Set(themeColors).size).toBe(THEME_MODES.length);
    for (const mode of THEME_MODES) expect(bootstrap).toContain(`"${mode}"`);
    for (const color of themeColors) expect(bootstrap).toContain(color);
  });
});
