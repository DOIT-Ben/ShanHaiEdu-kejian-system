import { beforeEach, describe, expect, it, vi } from "vitest";
import { downloadCreationResult } from "@/features/creation-studio/downloadCreationResult";
import { downloadExampleFile } from "@/shared/lib/downloadExampleFile";

vi.mock("@/shared/lib/downloadExampleFile", () => ({
  downloadExampleFile: vi.fn(),
}));

const mockDownloadExampleFile = vi.mocked(downloadExampleFile);

describe("downloadCreationResult", () => {
  beforeEach(() => mockDownloadExampleFile.mockReset());

  it("静态视频素材只下载关键帧说明", () => {
    downloadCreationResult({ candidate: 1, ratio: "16:9", title: "视频创作台", type: "video" });

    expect(mockDownloadExampleFile).toHaveBeenCalledWith(
      "视频创作台_关键帧2_说明.txt",
      expect.stringContaining("当前仅为关键帧示意，视频尚未生成"),
    );
    expect(mockDownloadExampleFile.mock.calls[0]?.[1]).not.toContain("视频预览说明");
  });
});
