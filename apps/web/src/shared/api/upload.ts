import { AppError } from "./AppError";

/** 直传签名地址（上传会话第二步）；签名 URL 不落库、不持久化。 */
export async function uploadToSignedUrl(input: {
  url: string;
  file: File;
  headers?: Record<string, string>;
}): Promise<void> {
  let response: Response;
  try {
    response = await fetch(input.url, {
      method: "PUT",
      headers: input.headers ?? {},
      body: input.file,
    });
  } catch (error) {
    throw AppError.fromUnknown(error);
  }
  if (!response.ok) {
    throw new AppError({
      code: "UPLOAD_FAILED",
      message: "文件上传失败，请重试。",
      status: response.status,
      retryable: true,
    });
  }
}
