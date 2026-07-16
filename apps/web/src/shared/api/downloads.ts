import { client, unwrap } from "./client";
import type { DownloadAuthorization } from "./types";

/**
 * 文件下载统一走短时授权（不长期暴露文件地址）。
 */
export async function authorizeDownload(fileObjectId: string): Promise<DownloadAuthorization> {
  const result = await client.POST("/file-objects/{fileObjectId}/download-authorizations", {
    params: { path: { fileObjectId } },
  });
  return unwrap(result).data;
}

export async function downloadFileObject(fileObjectId: string, fileName?: string): Promise<void> {
  const auth = await authorizeDownload(fileObjectId);
  const anchor = document.createElement("a");
  anchor.href = auth.url;
  anchor.rel = "noopener";
  if (fileName) anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}
