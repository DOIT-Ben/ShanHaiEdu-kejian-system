import { afterEach, describe, expect, it, vi } from "vitest";
import { downloadRemoteFile } from "@/shared/lib/downloadRemoteFile";

describe("downloadRemoteFile", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("通过 fetch 获取跨域媒体 Blob 后触发本地下载", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(new Blob(["video"], { type: "video/mp4" }), {
        headers: { "content-type": "video/mp4" },
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await downloadRemoteFile({
      acceptedMimeTypes: ["video/*"],
      filename: "课堂/导入.mp4",
      url: "https://cdn.example.com/final.mp4",
    });

    expect(fetchMock).toHaveBeenCalledWith("https://cdn.example.com/final.mp4", {
      headers: { Accept: "video/*" },
    });
    expect(click).toHaveBeenCalledOnce();
    expect(document.querySelector("a")).toBeNull();
  });

  it("跨域请求失败时不退回会跳转页面的链接下载", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(
      downloadRemoteFile({
        acceptedMimeTypes: ["video/*"],
        filename: "课堂导入.mp4",
        url: "https://cdn.example.com/final.mp4",
      }),
    ).rejects.toMatchObject({ reason: "network" });
    expect(click).not.toHaveBeenCalled();
  });

  it("拒绝与声明类型不一致的响应", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html>login</html>", {
          headers: { "content-type": "text/html" },
          status: 200,
        }),
      ),
    );

    await expect(
      downloadRemoteFile({
        acceptedMimeTypes: ["video/*"],
        filename: "课堂导入.mp4",
        url: "https://cdn.example.com/final.mp4",
      }),
    ).rejects.toMatchObject({
      reason: "unsupported_type",
    });
    expect(click).not.toHaveBeenCalled();
  });
});
