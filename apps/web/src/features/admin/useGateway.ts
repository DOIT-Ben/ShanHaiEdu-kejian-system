import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, qk, unwrap } from "@/shared/api";
import type { paths } from "@/shared/api/generated";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

type ProviderCreateBody =
  NonNullable<paths["/admin/model-gateway/providers"]["post"]["requestBody"]>["content"]["application/json"];
type ProviderUpdateBody =
  NonNullable<paths["/admin/model-gateway/providers/{providerId}"]["patch"]["requestBody"]>["content"]["application/json"];
type ModelUpdateBody =
  NonNullable<paths["/admin/model-gateway/models/{modelId}"]["patch"]["requestBody"]>["content"]["application/json"];
type RouteCreateBody =
  NonNullable<paths["/admin/model-gateway/routes"]["post"]["requestBody"]>["content"]["application/json"];
type RouteSimulateBody =
  NonNullable<paths["/admin/model-gateway/routes/simulate"]["post"]["requestBody"]>["content"]["application/json"];
type BudgetsUpdateBody =
  NonNullable<paths["/admin/model-gateway/budgets"]["put"]["requestBody"]>["content"]["application/json"];

export type { ProviderCreateBody, ProviderUpdateBody, RouteCreateBody, RouteSimulateBody, BudgetsUpdateBody };

export function useGatewayOverview() {
  return useQuery({
    queryKey: qk.admin.gatewayOverview,
    queryFn: async () => {
      const result = await client.GET("/admin/model-gateway/overview", {});
      return unwrap(result).data;
    },
  });
}

export function useProviders() {
  return useQuery({
    queryKey: qk.admin.providers,
    queryFn: async () => {
      const result = await client.GET("/admin/model-gateway/providers", {});
      return unwrap(result).data;
    },
  });
}

export function useCreateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: ProviderCreateBody) => {
      const result = await client.POST("/admin/model-gateway/providers", { body: input });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.providers });
      void queryClient.invalidateQueries({ queryKey: qk.admin.gatewayOverview });
    },
  });
}

export function useUpdateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { providerId: string; patch: ProviderUpdateBody }) => {
      const result = await client.PATCH("/admin/model-gateway/providers/{providerId}", {
        params: { path: { providerId: input.providerId } },
        body: input.patch,
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.providers });
      void queryClient.invalidateQueries({ queryKey: qk.admin.gatewayOverview });
    },
  });
}

export function useTestProviderConnection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (providerId: string) => {
      const result = await client.POST("/admin/model-gateway/providers/{providerId}/connection-tests", {
        params: {
          path: { providerId },
          header: { "Idempotency-Key": createIdempotencyKey("conntest") },
        },
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.tasks.mine });
    },
  });
}

export function useModels() {
  return useQuery({
    queryKey: qk.admin.models,
    queryFn: async () => {
      const result = await client.GET("/admin/model-gateway/models", {});
      return unwrap(result).data;
    },
  });
}

export function useUpdateModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { modelId: string; patch: ModelUpdateBody }) => {
      const result = await client.PATCH("/admin/model-gateway/models/{modelId}", {
        params: { path: { modelId: input.modelId } },
        body: input.patch,
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.models });
    },
  });
}

export function useRoutes() {
  return useQuery({
    queryKey: qk.admin.routes,
    queryFn: async () => {
      const result = await client.GET("/admin/model-gateway/routes", {});
      return unwrap(result).data;
    },
  });
}

export function useSaveRoute() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { routePolicyId?: string; body: RouteCreateBody }) => {
      if (input.routePolicyId) {
        const result = await client.PUT("/admin/model-gateway/routes/{routePolicyId}", {
          params: { path: { routePolicyId: input.routePolicyId } },
          body: input.body,
        });
        return unwrap(result).data;
      }
      const result = await client.POST("/admin/model-gateway/routes", { body: input.body });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.routes });
      void queryClient.invalidateQueries({ queryKey: qk.admin.gatewayOverview });
    },
  });
}

export function useSimulateRoute() {
  return useMutation({
    mutationFn: async (input: RouteSimulateBody) => {
      const result = await client.POST("/admin/model-gateway/routes/simulate", { body: input });
      return unwrap(result).data;
    },
  });
}

export function useBudgets() {
  return useQuery({
    queryKey: qk.admin.budgets,
    queryFn: async () => {
      const result = await client.GET("/admin/model-gateway/budgets", {});
      return unwrap(result).data;
    },
  });
}

export function useSaveBudgets() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: BudgetsUpdateBody) => {
      const result = await client.PUT("/admin/model-gateway/budgets", { body: input });
      return unwrap(result).data;
    },
    onSuccess: (budgets) => {
      queryClient.setQueryData(qk.admin.budgets, budgets);
    },
  });
}

export interface ModelRunFilters {
  capability?: string;
  provider_id?: string;
  status?: string;
  project_id?: string;
  fallback_only?: boolean;
}

export function useModelRuns(filters: ModelRunFilters = {}) {
  return useQuery({
    queryKey: qk.admin.modelRuns(filters as Record<string, unknown>),
    queryFn: async () => {
      const result = await client.GET("/admin/model-gateway/runs", {
        params: {
          query: {
            capability: filters.capability,
            provider_id: filters.provider_id,
            status: filters.status,
            project_id: filters.project_id,
            fallback_only: filters.fallback_only || undefined,
            page_size: 30,
          },
        },
      });
      return unwrap(result).data;
    },
  });
}

export function useModelRunDetail(modelRunId: string | null) {
  return useQuery({
    queryKey: qk.admin.modelRunDetail(modelRunId ?? "none"),
    queryFn: async () => {
      const result = await client.GET("/admin/model-gateway/runs/{modelRunId}", {
        params: { path: { modelRunId: modelRunId! } },
      });
      return unwrap(result).data;
    },
    enabled: Boolean(modelRunId),
  });
}
