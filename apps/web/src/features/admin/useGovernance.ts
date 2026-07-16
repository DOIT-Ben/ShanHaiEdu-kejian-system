import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, qk, unwrap } from "@/shared/api";

export function useWorkflows() {
  return useQuery({
    queryKey: qk.admin.workflows,
    queryFn: async () => {
      const result = await client.GET("/admin/workflows", {});
      return unwrap(result).data;
    },
  });
}

export function useWorkflowDetail(workflowId: string) {
  return useQuery({
    queryKey: qk.admin.workflowDetail(workflowId),
    queryFn: async () => {
      const result = await client.GET("/admin/workflows/{workflowId}", { params: { path: { workflowId } } });
      return unwrap(result).data;
    },
  });
}

export function useAdminUsers(filters: { role?: "teacher" | "template_admin" | "system_admin" | "audit_admin"; status?: "active" | "disabled"; keyword?: string } = {}) {
  return useQuery({
    queryKey: qk.admin.users(filters as Record<string, unknown>),
    queryFn: async () => {
      const result = await client.GET("/admin/users", {
        params: { query: { ...filters, keyword: filters.keyword || undefined } },
      });
      return unwrap(result).data;
    },
  });
}

export function useUpdateAdminUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      userId: string;
      role?: "teacher" | "template_admin" | "system_admin" | "audit_admin";
      status?: "active" | "disabled";
      reason: string;
    }) => {
      const result = await client.PATCH("/admin/users/{userId}", {
        params: { path: { userId: input.userId } },
        body: { role: input.role, status: input.status, reason: input.reason },
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.admin.usersRoot });
    },
  });
}

export function useOrganizations() {
  return useQuery({
    queryKey: qk.admin.organizations,
    queryFn: async () => {
      const result = await client.GET("/admin/organizations", {});
      return unwrap(result).data;
    },
  });
}

export function useAuditLog(filters: { action?: string; object_type?: string; keyword?: string } = {}) {
  return useQuery({
    queryKey: qk.admin.audit(filters as Record<string, unknown>),
    queryFn: async () => {
      const result = await client.GET("/admin/audit", {
        params: { query: { ...filters, keyword: filters.keyword || undefined, page_size: 50 } },
      });
      return unwrap(result).data;
    },
  });
}
