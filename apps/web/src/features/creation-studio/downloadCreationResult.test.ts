import { render } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getCreationImageAsset } from "@/assets/creation/catalog";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import { downloadCreationResult } from "@/features/creation-studio/downloadCreationResult";
import { downloadExampleFile } from "@/shared/lib/downloadExampleFile";

vi.mock("@/shared/lib/downloadExampleFile", () => ({
  downloadExampleFile: vi.fn(),
}));

const mockDownloadExampleFile = vi.mocked(downloadExampleFile);

describe("downloadCreationResult", () => {
  beforeEach(() => {
    mockDownloadExampleFile.mockReset();
    vi.spyOn(window, "alert").mockImplementation(() => undefined);
  });

  afterEach(() => vi.restoreAllMocks());

  it("静态视频素材只下载关键帧说明", () => {
    downloadCreationResult({ candidate: 1, ratio: "16:9", title: "视频创作台", type: "video" });

    expect(mockDownloadExampleFile).toHaveBeenCalledWith(
      "视频创作台_关键帧2_说明.txt",
      expect.stringContaining("当前仅为关键帧示意，视频尚未生成"),
    );
    expect(mockDownloadExampleFile.mock.calls[0]?.[1]).not.toContain("视频预览说明");
  });

  it("下载当前主视觉实际展示的候选素材，而不是程序化占位图", () => {
    const clicked: { download?: string; href?: string } = {};
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.download = this.download;
      clicked.href = this.href;
    });
    render(
      createElement(
        "div",
        { "data-testid": "creation-main-visual" },
        createElement(CreativeResultVisual, { type: "image", variant: 1 }),
      ),
    );

    const result = downloadCreationResult({
      candidate: 1,
      ratio: "4:3",
      title: "图片创作台",
      type: "image",
    });

    expect(result).toEqual({ status: "started" });
    expect(clicked.download).toBe("图片创作台_作品2.webp");
    expect(clicked.href).toContain(getCreationImageAsset(1).src);
    expect(clicked.href).not.toContain("<svg");
  });

  it("拒绝跨域或缺失图片地址并给出可理解提示", () => {
    const result = downloadCreationResult({
      candidate: 0,
      imageSource: "https://cdn.example.com/foreign.webp",
      ratio: "1:1",
      title: "图片创作台",
      type: "image",
    });

    expect(result.status).toBe("unavailable");
    expect(window.alert).toHaveBeenCalledWith(
      "当前作品图片暂时无法直接下载，请保存到项目后从成果页下载。",
    );
  });
});
