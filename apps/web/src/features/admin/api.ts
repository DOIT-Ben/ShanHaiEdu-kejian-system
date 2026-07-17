import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function useContentPackages() {
  return useQuery({
    queryKey: qk.admin.contentPackages,
    queryFn: async () => {
      const result = unwrap(await client.GET("/admin/content-packages"));
      return result.data.items;
    },
    refetchInterval: (query) =>
      query.state.data?.some((pkg) => pkg.status === "checking") ? 2_500 : false,
  });
}

export function useContentPackage(id: string | null) {
  return useQuery({
    queryKey: qk.admin.contentPackage(id ?? "none"),
    enabled: Boolean(id),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/admin/content-packages/{content_package_id}", {
          params: { path: { content_package_id: id! } },
        }),
      );
      return result.data;
    },
    refetchInterval: (query) =>
      query.state.data?.package.status === "checking" ? 2_000 : false,
  });
}

export function useImportContentPackage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { title: string; domain: string; definition: unknown }) => {
      const result = unwrap(
        await client.POST("/admin/content-packages", {
          body: {
            title: input.title,
            domain: input.domain as never,
            definition: input.definition as never,
          },
          params: { header: { "Idempotency-Key": createIdempotencyKey("cp-import") } },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.contentPackages });
    },
  });
}

export function useDryRunContentPackage(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const result = unwrap(
        await client.POST("/admin/content-packages/{content_package_id}/dry-run", {
          params: { path: { content_package_id: id }, header: { "Idempotency-Key": createIdempotencyKey("cp-dryrun") } },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.contentPackage(id) });
      void queryClient.invalidateQueries({ queryKey: qk.admin.contentPackages });
    },
  });
}

export function usePublishContentPackage(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const result = unwrap(
        await client.POST("/admin/content-packages/{content_package_id}/publish", {
          params: { path: { content_package_id: id }, header: { "Idempotency-Key": createIdempotencyKey("cp-publish") } },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.contentPackage(id) });
      void queryClient.invalidateQueries({ queryKey: qk.admin.contentPackages });
    },
  });
}

export function useAdminWorkflows() {
  return useQuery({
    queryKey: qk.admin.workflows,
    queryFn: async () => {
      const result = unwrap(await client.GET("/admin/workflows"));
      return result.data.items;
    },
  });
}

export function useAdminWorkflow(id: string | null) {
  return useQuery({
    queryKey: qk.admin.workflow(id ?? "none"),
    enabled: Boolean(id),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/admin/workflows/{workflow_id}", {
          params: { path: { workflow_id: id! } },
        }),
      );
      return result.data;
    },
  });
}

export function useModelServiceOverview() {
  return useQuery({
    queryKey: qk.admin.modelOverview,
    queryFn: async () => {
      const result = unwrap(await client.GET("/admin/model-services/overview"));
      return result.data;
    },
  });
}

export function useProviders() {
  return useQuery({
    queryKey: qk.admin.providers,
    queryFn: async () => {
      const result = unwrap(await client.GET("/admin/providers"));
      return result.data.items;
    },
  });
}

export function useUpdateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      providerId: string;
      etag: string;
      patch: { display_name?: string; base_url?: string; secret?: string; enabled?: boolean };
    }) => {
      const result = unwrap(
        await client.PATCH("/admin/providers/{provider_id}", {
          params: {
            path: { provider_id: input.providerId },
            header: { "If-Match": input.etag, "Idempotency-Key": createIdempotencyKey("provider") },
          },
          body: input.patch,
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.providers });
      void queryClient.invalidateQueries({ queryKey: qk.admin.modelOverview });
    },
  });
}

export function useTestProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (providerId: string) => {
      const result = unwrap(
        await client.POST("/admin/providers/{provider_id}/test", {
          params: { path: { provider_id: providerId }, header: { "Idempotency-Key": createIdempotencyKey("provider-test") } },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.providers });
    },
  });
}

export function useModelCatalog() {
  return useQuery({
    queryKey: qk.admin.models,
    queryFn: async () => {
      const result = unwrap(await client.GET("/admin/models"));
      return result.data.items;
    },
  });
}

export function useUsageOverview() {
  return useQuery({
    queryKey: qk.admin.usage,
    queryFn: async () => {
      const result = unwrap(await client.GET("/admin/usage/overview"));
      return result.data;
    },
  });
}

export function useModelRuns() {
  return useQuery({
    queryKey: qk.admin.modelRuns(),
    queryFn: async () => {
      const result = unwrap(await client.GET("/admin/model-runs"));
      return result.data.items;
    },
  });
}

export function useAdminUsers() {
  return useQuery({
    queryKey: qk.admin.users,
    queryFn: async () => {
      const result = unwrap(await client.GET("/admin/users"));
      return result.data.items;
    },
  });
}

export function useAuditEvents() {
  return useQuery({
    queryKey: qk.admin.audit(),
    queryFn: async () => {
      const result = unwrap(await client.GET("/admin/audit-events"));
      return result.data.items;
    },
  });
}
