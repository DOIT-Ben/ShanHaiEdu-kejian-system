import { render } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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

  it("静态视频素材只下载关键帧说明", async () => {
    await downloadCreationResult({
      candidate: 1,
      ratio: "16:9",
      title: "视频创作台",
      type: "video",
    });

    expect(mockDownloadExampleFile).toHaveBeenCalledWith(
      "视频创作台_关键帧2_说明.txt",
      expect.stringContaining("当前仅为关键帧示意，视频尚未生成"),
    );
    expect(mockDownloadExampleFile.mock.calls[0]?.[1]).not.toContain("视频预览说明");
  });

  it("按当前比例和视觉焦点裁切真实候选后再下载", async () => {
    const clicked: { download?: string; href?: string } = {};
    const drawImage = vi.fn();
    let exportedSize: { height: number; width: number } | undefined;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.download = this.download;
      clicked.href = this.href;
    });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      drawImage,
      imageSmoothingEnabled: false,
      imageSmoothingQuality: "low",
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(function (
      this: HTMLCanvasElement,
      callback,
      type,
    ) {
      exportedSize = { height: this.height, width: this.width };
      callback(new Blob(["cropped-webp"], { type: type ?? "image/webp" }));
    });
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:cropped-candidate");
    const view = render(
      createElement(
        "div",
        { "data-testid": "creation-main-visual" },
        createElement(CreativeResultVisual, { type: "image", variant: 1 }),
      ),
    );
    const renderedImage = view.container.querySelector("img");
    expect(renderedImage).not.toBeNull();
    if (!renderedImage) return;
    Object.defineProperties(renderedImage, {
      complete: { configurable: true, value: true },
      naturalHeight: { configurable: true, value: 1086 },
      naturalWidth: { configurable: true, value: 1448 },
    });

    const result = await downloadCreationResult({
      candidate: 1,
      ratio: "16:9",
      title: "图片创作台",
      type: "image",
    });

    expect(result).toEqual({ status: "started" });
    expect(clicked.download).toBe("图片创作台_作品2.webp");
    expect(clicked.href).toBe("blob:cropped-candidate");
    expect(exportedSize).toEqual({ height: 900, width: 1600 });
    expect(drawImage).toHaveBeenCalledWith(
      renderedImage,
      expect.any(Number),
      expect.any(Number),
      expect.any(Number),
      expect.any(Number),
      0,
      0,
      1600,
      900,
    );
  });

  it("拒绝跨域或缺失图片地址并给出可理解提示", async () => {
    const result = await downloadCreationResult({
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
