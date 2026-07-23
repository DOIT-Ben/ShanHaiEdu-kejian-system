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

  it("真实课题只把已接入素材标为课堂示例，不冒充当前课题结果", () => {
    render(<VideoScenePreview topic="圆的面积" variant={2} />);

    const preview = screen.getByRole("img", {
      name: "果汁标签课堂示例，仅作“圆的面积”画面节奏参考；当前课题视频尚未生成",
    });
    expect(preview.querySelector("img")).toHaveAttribute("src", creationVideoShotAssets[2]);
    expect(screen.getByText("课堂示例参考 · 当前课题尚未生成")).toBeInTheDocument();
    expect(screen.getByText("果汁标签课堂示例 · 非“圆的面积”生成结果")).toBeInTheDocument();
  });
});
