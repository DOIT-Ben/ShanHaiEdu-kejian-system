import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { creationPptContentAssets, creationPptCoverAssets } from "@/assets/creation/catalog";
import { PercentSlidePreview } from "@/features/home/components/PercentSlidePreview";

describe("PercentSlidePreview", () => {
  it("按页面类型选择正式封面和正文示例素材", () => {
    const { rerender } = render(<PercentSlidePreview page={0} variant={1} />);
    const cover = screen.getByRole("img", { name: /三瓶果汁组成的百分数课件封面/ });
    expect(cover.querySelector("img")).toHaveAttribute("src", creationPptCoverAssets[1]);

    rerender(<PercentSlidePreview page={2} />);
    const content = screen.getByRole("img", { name: /百格图中涂出百分之三十七/ });
    expect(content.querySelector("img")).toHaveAttribute("src", creationPptContentAssets[1]);
  });

  it("真实课题预览不使用固定示例素材", () => {
    render(<PercentSlidePreview page={2} topic="圆的面积" />);

    const preview = screen.getByRole("img", { name: "圆的面积课堂课件页面预览" });
    expect(preview.querySelector("img")).toBeNull();
    expect(screen.getByText("圆的面积")).toBeInTheDocument();
  });

  it("缩略图文字跟随组件宽度而不是浏览器宽度", () => {
    render(<PercentSlidePreview page={2} topic="圆的面积" />);

    const preview = screen.getByRole("img", { name: "圆的面积课堂课件页面预览" });
    expect(preview.className).toContain("[container-type:inline-size]");
    expect(screen.getByText("圆的面积").className).toContain("cqw");
    expect(screen.getByText("圆的面积").className).not.toContain("vw");
  });

  it("支持给 PPT 缩略图传入懒加载策略", () => {
    render(<PercentSlidePreview loading="lazy" page={2} />);

    expect(
      screen.getByRole("img", { name: /百格图中涂出百分之三十七/ }).querySelector("img"),
    ).toHaveAttribute("loading", "lazy");
  });
});
