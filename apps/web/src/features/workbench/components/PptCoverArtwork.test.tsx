import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { creationPptCoverAssets } from "@/assets/creation/catalog";
import { PptCoverArtwork } from "@/features/workbench/components/PptCoverArtwork";

describe("PptCoverArtwork", () => {
  it("示例模式显示正式封面素材并保留独立文字层", () => {
    render(
      <PptCoverArtwork demo variant={3}>
        <h2>认识百分数</h2>
      </PptCoverArtwork>,
    );

    const cover = screen.getByRole("group", { name: "课堂发现课件封面预览" });
    expect(cover.querySelector("img")).toHaveAttribute("src", creationPptCoverAssets[2]);
    expect(screen.getByRole("heading", { name: "认识百分数" })).toBeInTheDocument();
  });

  it("非示例模式不把固定封面当作课题结果", () => {
    render(
      <PptCoverArtwork demo={false} variant={2}>
        <h2>圆的面积</h2>
      </PptCoverArtwork>,
    );

    const cover = screen.getByRole("group", { name: "课件封面预览" });
    expect(cover.querySelector("img")).toBeNull();
    expect(screen.getByRole("heading", { name: "圆的面积" })).toBeInTheDocument();
  });
});
