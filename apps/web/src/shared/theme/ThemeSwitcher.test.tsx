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
});
