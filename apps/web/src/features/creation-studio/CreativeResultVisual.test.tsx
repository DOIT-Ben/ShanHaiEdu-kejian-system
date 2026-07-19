import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";

describe("CreativeResultVisual", () => {
  it("静态视频素材只作为关键帧示意，不显示播放控件", () => {
    render(<CreativeResultVisual type="video" />);

    const preview = screen.getByRole("img", {
      name: "课堂导入关键帧示意，视频尚未生成",
    });
    expect(preview.querySelector("svg")).toBeNull();
    expect(screen.getByText("关键帧示意 · 视频尚未生成")).toBeInTheDocument();
  });
});
