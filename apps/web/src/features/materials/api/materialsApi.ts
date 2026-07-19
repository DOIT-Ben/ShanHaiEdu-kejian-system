import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult, unwrapApiResultWithResponse } from "@/shared/api/client";

export type UploadSessionDto = components["schemas"]["UploadSession"];
export type AcceptedJobDto = components["schemas"]["AcceptedJobEnvelope"]["data"];
export type FileAssetDto = components["schemas"]["FileAsset"];
export type MaterialParseVersionDto = components["schemas"]["MaterialParseVersion"];
export type CreateUploadSessionRequest = components["schemas"]["CreateUploadSessionRequest"];

async function readFileBuffer(file: File): Promise<ArrayBuffer> {
  if (typeof file.arrayBuffer === "function") return file.arrayBuffer();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("教材文件无法读取"));
    reader.onload = () => {
      if (reader.result instanceof ArrayBuffer) resolve(reader.result);
      else reject(new Error("教材文件无法读取"));
    };
    reader.readAsArrayBuffer(file);
  });
}

export async function sha256File(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await readFileBuffer(file));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function createMaterialUploadSession({
  idempotencyKey,
  input,
  projectId,
}: {
  idempotencyKey: string;
  input: CreateUploadSessionRequest;
  projectId: string;
}): Promise<UploadSessionDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/projects/{project_id}/materials/uploads", {
      body: input,
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { project_id: projectId },
      },
    }),
  );
  return response.data;
}

export async function uploadMaterialFile(session: UploadSessionDto, file: File): Promise<string> {
  const response = await fetch(session.upload_url, {
    body: file,
    headers: session.required_headers,
    method: session.method,
  });
  if (!response.ok) {
    throw new Error("教材没有上传完成，请检查网络后重试");
  }
  const etag = response.headers.get("ETag")?.trim();
  if (!etag) {
    throw new Error("教材已传输，但存储服务没有返回校验标识");
  }
  return etag;
}

export async function confirmMaterialUpload({
  etag,
  file,
  idempotencyKey,
  materialId,
  projectId,
  sha256,
  uploadSessionId,
}: {
  etag: string;
  file: File;
  idempotencyKey: string;
  materialId: string;
  projectId: string;
  sha256: string;
  uploadSessionId: string;
}): Promise<AcceptedJobDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/projects/{project_id}/materials/{material_id}/confirm", {
      body: {
        etag,
        sha256,
        size_bytes: file.size,
        upload_session_id: uploadSessionId,
      },
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { material_id: materialId, project_id: projectId },
      },
    }),
  );
  return response.data;
}

export async function getSourceMaterialFileAsset({
  materialId,
  projectId,
}: {
  materialId: string;
  projectId: string;
}): Promise<{ asset: FileAssetDto; etag?: string }> {
  const response = unwrapApiResultWithResponse(
    await apiClient.GET("/projects/{project_id}/materials/{material_id}/file-asset", {
      params: { path: { material_id: materialId, project_id: projectId } },
    }),
  );
  return { asset: response.body.data, etag: response.etag };
}

export async function listMaterialParseVersions({
  materialId,
  projectId,
}: {
  materialId: string;
  projectId: string;
}): Promise<MaterialParseVersionDto[]> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}/materials/{material_id}/parse-versions", {
      params: { path: { material_id: materialId, project_id: projectId } },
    }),
  );
  return response.data.items;
}
