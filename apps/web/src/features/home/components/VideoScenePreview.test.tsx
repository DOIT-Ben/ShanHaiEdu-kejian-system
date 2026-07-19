import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { creationVideoShotAssets } from "@/assets/creation/catalog";
import { VideoScenePreview } from "@/features/home/components/VideoScenePreview";

describe("VideoScenePreview", () => {
  it("示例模式按镜头显示正式故事帧", () => {
    render(<VideoScenePreview variant={3} />);

    const preview = screen.getByRole("img", { name: /等待回答的课堂首问/ });
    expect(preview.querySelector("img")).toHaveAttribute("src", creationVideoShotAssets[3]);
  });

  it("真实课题预览不使用固定故事帧", () => {
    render(<VideoScenePreview topic="圆的面积" variant={2} />);

    const preview = screen.getByRole("img", { name: "圆的面积课堂导入画面预览" });
    expect(preview.querySelector("img")).toBeNull();
    expect(screen.getByText("圆的面积")).toBeInTheDocument();
  });
});
