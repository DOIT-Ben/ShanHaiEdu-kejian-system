import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { creationVideoShotAssets } from "@/assets/creation/catalog";
import { VideoScenePreview } from "@/features/home/components/VideoScenePreview";

describe("VideoScenePreview", () => {
  it("示例模式按镜头显示正式故事帧", () => {
    render(<VideoScenePreview variant={3} />);

    const preview = screen.getByRole("img", { name: /等待回答的课堂首问.*视频尚未生成/ });
    expect(preview.querySelector("img")).toHaveAttribute("src", creationVideoShotAssets[3]);
    expect(preview.querySelector("svg")).toBeNull();
    expect(screen.getByText("关键帧示意 · 视频尚未生成")).toBeInTheDocument();
  });

  it("真实课题预览使用已接入的关键帧素材并叠加课题", () => {
    render(<VideoScenePreview topic="圆的面积" variant={2} />);

    const preview = screen.getByRole("img", {
      name: "圆的面积课堂导入关键帧示意，视频尚未生成",
    });
    expect(preview.querySelector("img")).toHaveAttribute("src", creationVideoShotAssets[2]);
    expect(screen.getByText(/圆的面积.*关键帧参考/)).toBeInTheDocument();
  });
});
