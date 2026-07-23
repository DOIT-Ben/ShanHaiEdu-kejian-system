import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { ThemeSwitcher } from "@/shared/theme/ThemeSwitcher";
import { DEFAULT_THEME, THEME_STORAGE_KEY } from "@/shared/theme/theme";

describe("主题切换器", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.dataset.theme = DEFAULT_THEME;
  });

  it("从护眼模式切换到黑夜模式并持久化", async () => {
    const user = userEvent.setup();
    render(<ThemeSwitcher />);

    await user.click(screen.getByRole("button", { name: "切换主题，当前护眼模式" }));
    await user.click(screen.getByRole("menuitemradio", { name: "黑夜模式" }));

    expect(document.documentElement.dataset.theme).toBe("night");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("night");
    expect(screen.getByRole("button", { name: "切换主题，当前黑夜模式" })).toBeVisible();
  });

  it("可切换到高级简约模式并保留清晰的当前状态", async () => {
    const user = userEvent.setup();
    render(<ThemeSwitcher />);

    await user.click(screen.getByRole("button", { name: "切换主题，当前护眼模式" }));
    await user.click(screen.getByRole("menuitemradio", { name: "高级简约模式" }));

    expect(document.documentElement.dataset.theme).toBe("atelier");
    expect(document.documentElement.style.colorScheme).toBe("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("atelier");
    expect(screen.getByRole("button", { name: "切换主题，当前高级简约模式" })).toBeVisible();
  });

  it.each([
    ["删除主题键", THEME_STORAGE_KEY],
    ["清空浏览器存储", null],
  ])("%s时跨标签恢复护眼模式", (_, key) => {
    render(<ThemeSwitcher />);
    document.documentElement.dataset.theme = "night";

    window.dispatchEvent(new StorageEvent("storage", { key, newValue: null }));

    expect(document.documentElement.dataset.theme).toBe(DEFAULT_THEME);
  });

  it("可按需显示当前主题文字，帮助触屏用户识别入口", () => {
    render(<ThemeSwitcher showLabel />);
    expect(screen.getByText("护眼")).toBeVisible();
  });

  it("入口与菜单项都提供至少 44px 的触控高度", async () => {
    const user = userEvent.setup();
    render(<ThemeSwitcher />);

    const trigger = screen.getByRole("button", { name: "切换主题，当前护眼模式" });
    expect(trigger.className).toContain("h-11");
    expect(trigger.className).toContain("min-w-11");
    await user.click(trigger);
    expect(screen.getByRole("menuitemradio", { name: "白天模式" }).className).toContain("min-h-11");
  });
});
