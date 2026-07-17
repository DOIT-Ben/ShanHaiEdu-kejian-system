import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk, AppError } from "@/shared/api";
import { uploadToSignedUrl } from "@/shared/api/upload";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function useMaterial(projectId: string) {
  return useQuery({
    queryKey: qk.projects.material(projectId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/projects/{project_id}/material", {
          params: { path: { project_id: projectId } },
        }),
      );
      return result.data.material;
    },
    refetchInterval: (query) => {
      const material = query.state.data;
      if (!material) return false;
      return material.status === "uploading" || material.status === "scanning" || material.status === "parsing"
        ? 2_000
        : false;
    },
  });
}

/** 上传三步链：创建会话 → 直传 → 完成通知（202 解析任务）。 */
export function useUploadMaterial(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      if (file.type !== "application/pdf") {
        throw new AppError({
          code: "UNSUPPORTED_FILE_TYPE",
          message: "目前只支持 PDF 教材。",
          status: 422,
          retryable: false,
        });
      }
      const session = unwrap(
        await client.POST("/projects/{project_id}/upload-sessions", {
          params: { path: { project_id: projectId }, header: { "Idempotency-Key": createIdempotencyKey("upload") } },
          body: { file_name: file.name, size_bytes: file.size, mime_type: file.type },
        }),
      );
      const { upload_url, upload_session_id, required_headers } = session.data;
      await uploadToSignedUrl({
        url: upload_url,
        file,
        headers: (required_headers as Record<string, string> | undefined) ?? {},
      });
      const completed = unwrap(
        await client.POST("/upload-sessions/{upload_session_id}/complete", {
          params: { path: { upload_session_id } },
          body: { size_bytes: file.size },
        }),
      );
      return completed.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.material(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
    },
  });
}

export function useConfirmScope(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const result = unwrap(
        await client.POST("/projects/{project_id}/material/confirm-scope", {
          params: { path: { project_id: projectId }, header: { "Idempotency-Key": createIdempotencyKey("confirm-scope") } },
        }),
      );
      return result.data.material;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.material(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.division(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.workflow(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
    },
  });
}
