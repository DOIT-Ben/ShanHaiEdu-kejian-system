import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownPreview } from "@/features/workbench/components/MarkdownPreview";

describe("MarkdownPreview", () => {
  it("把文档标题降级到页面 h1 之后的层级", () => {
    render(
      <MarkdownPreview
        markdown={"# 百分数的意义\n\n## 教学目标\n\n### 课堂探究\n\n理解百分数。"}
      />,
    );

    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "百分数的意义" })).toBeVisible();
    expect(screen.getByRole("heading", { level: 3, name: "教学目标" })).toBeVisible();
    expect(screen.getByRole("heading", { level: 4, name: "课堂探究" })).toBeVisible();
  });
});
