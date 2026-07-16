import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, qk, unwrap } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function useTemplates(filters: { status?: string; node_type?: string; keyword?: string } = {}) {
  return useQuery({
    queryKey: qk.admin.templates(filters as Record<string, unknown>),
    queryFn: async () => {
      const result = await client.GET("/admin/templates", {
        params: { query: { ...filters, keyword: filters.keyword || undefined } },
      });
      return unwrap(result).data;
    },
  });
}

export function useTemplateDetail(templateId: string) {
  return useQuery({
    queryKey: qk.admin.templateDetail(templateId),
    queryFn: async () => {
      const result = await client.GET("/admin/templates/{templateId}", { params: { path: { templateId } } });
      return unwrap(result).data;
    },
  });
}

export function useImportTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { name: string; node_type: string; content: string; description?: string }) => {
      const result = await client.POST("/admin/templates", { body: input });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.templatesRoot });
    },
  });
}

export function useUpdateTemplate(templateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { content?: string; name?: string; description?: string }) => {
      const result = await client.PATCH("/admin/templates/{templateId}", {
        params: { path: { templateId } },
        body: input,
      });
      return unwrap(result).data;
    },
    onSuccess: (detail) => {
      queryClient.setQueryData(qk.admin.templateDetail(templateId), detail);
      void queryClient.invalidateQueries({ queryKey: qk.admin.templatesRoot });
    },
  });
}

export function useTemplateDryRun(templateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const result = await client.POST("/admin/templates/{templateId}/dry-runs", {
        params: {
          path: { templateId },
          header: { "Idempotency-Key": createIdempotencyKey("dryrun") },
        },
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.templateDetail(templateId) });
    },
  });
}

export function usePublishTemplate(templateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { version: string; changelog?: string; override_reason?: string }) => {
      const result = await client.POST("/admin/templates/{templateId}/publish", {
        params: { path: { templateId } },
        body: input,
      });
      return unwrap(result).data;
    },
    onSuccess: (detail) => {
      queryClient.setQueryData(qk.admin.templateDetail(templateId), detail);
      void queryClient.invalidateQueries({ queryKey: qk.admin.templatesRoot });
    },
  });
}

export function useRollbackTemplate(templateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { to_version: string; reason: string }) => {
      const result = await client.POST("/admin/templates/{templateId}/rollback", {
        params: { path: { templateId } },
        body: input,
      });
      return unwrap(result).data;
    },
    onSuccess: (detail) => {
      queryClient.setQueryData(qk.admin.templateDetail(templateId), detail);
      void queryClient.invalidateQueries({ queryKey: qk.admin.templatesRoot });
    },
  });
}
