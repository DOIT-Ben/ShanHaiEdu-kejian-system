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

  it("为教学图片提供准确描述、自然尺寸、视觉焦点和懒加载策略", () => {
    render(<CreativeResultVisual loading="lazy" type="image" variant={1} />);

    const image = screen.getByRole("img", {
      name: "老师和两名学生在水果分份教具前进行课堂观察",
    });
    expect(image).toHaveAttribute("width", "1448");
    expect(image).toHaveAttribute("height", "1086");
    expect(image).toHaveAttribute("loading", "lazy");
    expect(image).toHaveStyle({ objectPosition: "50% 54%" });
  });
});
