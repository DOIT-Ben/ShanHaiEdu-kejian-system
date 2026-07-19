import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { HomeBrandHero } from "@/pages/home/HomeBrandHero";

describe("HomeBrandHero", () => {
  it("已有项目时把继续制作设为唯一主操作", () => {
    render(
      <MemoryRouter>
        <HomeBrandHero continueTo="/app/projects/project-a" hasProject />
      </MemoryRouter>,
    );

    const continueLink = screen.getByRole("link", { name: "继续当前课件" });
    const createLink = screen.getByRole("link", { name: "新建课件" });
    expect(continueLink).toHaveAttribute("href", "/app/projects/project-a");
    expect(continueLink.className).toContain("bg-[var(--sh-brand-700)]");
    expect(createLink.className).toContain("border");
    expect(createLink.className).not.toContain("bg-[var(--sh-brand-700)]");
  });

  it("没有项目时以上传教材为主操作", () => {
    render(
      <MemoryRouter>
        <HomeBrandHero continueTo="/app/projects" hasProject={false} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "上传教材开始制作" }).className).toContain(
      "bg-[var(--sh-brand-700)]",
    );
  });
});
