import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HomeBrandHero } from "@/pages/home/HomeBrandHero";

describe("HomeBrandHero", () => {
  it("已有项目时只呈现项目上下文，不抢占任务操作", () => {
    render(
      <HomeBrandHero hasProject lessonTitle="第 1 课时 · 百分数的意义" projectTitle="认识百分数" />,
    );

    expect(screen.getByRole("heading", { level: 1, name: "认识百分数" })).toBeInTheDocument();
    expect(screen.getByText("第 1 课时 · 百分数的意义")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("没有项目时只呈现开始备课上下文", () => {
    render(<HomeBrandHero hasProject={false} />);

    expect(
      screen.getByRole("heading", { level: 1, name: "开始第一份课堂项目" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
