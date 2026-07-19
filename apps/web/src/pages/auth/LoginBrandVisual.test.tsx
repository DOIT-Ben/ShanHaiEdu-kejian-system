import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { LoginVisualPanel } from "@/pages/auth/LoginBrandVisual";

describe("LoginBrandVisual", () => {
  it("使用正式课堂素材并提供准确的替代文本", () => {
    render(<LoginVisualPanel />);

    expect(
      screen.getByRole("img", { name: "老师带领两名学生观察数学材料的温暖课堂" }),
    ).toBeInTheDocument();
  });

  it("登录页不再引用旧占位 SVG", () => {
    const source = readFileSync(resolve(__dirname, "LoginPage.tsx"), "utf8");

    expect(source).not.toContain("slide-percent-cover.svg");
    expect(source).not.toContain("juice-observation.svg");
    expect(source).not.toContain('src="/assets/');
  });
});
