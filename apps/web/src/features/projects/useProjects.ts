import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, qk, unwrap, unwrapVoid } from "@/shared/api";
import type { Project } from "@/shared/api/types";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export interface ProjectListFilters {
  status?: "draft" | "active" | "archived";
  keyword?: string;
  sort?: "updated_desc" | "created_desc" | "name_asc";
}

export function useProjects(filters: ProjectListFilters = {}) {
  return useQuery({
    queryKey: qk.projects.list(filters as Record<string, unknown>),
    queryFn: async () => {
      const result = await client.GET("/projects", {
        params: {
          query: {
            status: filters.status,
            keyword: filters.keyword || undefined,
            sort: filters.sort,
          },
        },
      });
      return unwrap(result).data;
    },
  });
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: qk.projects.detail(projectId),
    queryFn: async () => {
      const result = await client.GET("/projects/{projectId}", { params: { path: { projectId } } });
      return unwrap(result).data;
    },
  });
}

export interface CreateProjectInput {
  name: string;
  grade: number;
  textbook_version: string;
  volume: string;
  execution_mode: "manual" | "semi_auto" | "full_auto_draft";
  budget_minor_units?: number;
  output_scope: { ppt: boolean; video: boolean };
  textbook_file_object_id?: string | null;
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateProjectInput): Promise<Project> => {
      const result = await client.POST("/projects", {
        params: { header: { "Idempotency-Key": createIdempotencyKey("proj") } },
        body: { subject: "primary_math", ...input },
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.root });
      void queryClient.invalidateQueries({ queryKey: qk.homeOverview });
    },
  });
}

export function useUpdateProject(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: Partial<CreateProjectInput> & { row_version: number }) => {
      const result = await client.PATCH("/projects/{projectId}", {
        params: { path: { projectId } },
        body: input,
      });
      return unwrap(result).data;
    },
    onSuccess: (project) => {
      queryClient.setQueryData(qk.projects.detail(projectId), project);
      void queryClient.invalidateQueries({ queryKey: qk.projects.root });
    },
  });
}

export function useArchiveProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (projectId: string) => {
      const result = await client.POST("/projects/{projectId}/archive", { params: { path: { projectId } } });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.root });
      void queryClient.invalidateQueries({ queryKey: qk.homeOverview });
    },
  });
}

export function useRestoreProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (projectId: string) => {
      const result = await client.POST("/projects/{projectId}/restore", { params: { path: { projectId } } });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.root });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (projectId: string) => {
      const result = await client.DELETE("/projects/{projectId}", { params: { path: { projectId } } });
      unwrapVoid(result);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.root });
      void queryClient.invalidateQueries({ queryKey: qk.homeOverview });
    },
  });
}
