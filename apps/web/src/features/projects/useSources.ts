import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AppError, client, qk, unwrap } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";
import type { DivisionContent } from "@/entities/content";

export function useTextbookEvidence(projectId: string) {
  return useQuery({
    queryKey: qk.projects.evidence(projectId),
    queryFn: async () => {
      const result = await client.GET("/projects/{projectId}/textbook-evidence/current", {
        params: { path: { projectId } },
      });
      return unwrap(result).data;
    },
    retry: (failureCount, error) => {
      if (error instanceof AppError && (error.status === 404 || error.isSessionExpired)) return false;
      return failureCount < 2;
    },
  });
}

export function useSubmitEvidenceCorrections(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      corrections: Array<{ page_number: number; field: string; corrected_value: string }>;
      row_version: number;
    }) => {
      const result = await client.POST("/projects/{projectId}/textbook-evidence/corrections", {
        params: { path: { projectId } },
        body: input,
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.evidence(projectId) });
    },
  });
}

export function useLessonDivision(projectId: string) {
  return useQuery({
    queryKey: qk.projects.division(projectId),
    queryFn: async () => {
      const result = await client.GET("/projects/{projectId}/lesson-divisions/current", {
        params: { path: { projectId } },
      });
      return unwrap(result).data;
    },
    retry: (failureCount, error) => {
      if (error instanceof AppError && (error.status === 404 || error.isSessionExpired)) return false;
      return failureCount < 2;
    },
  });
}

export function useDivisionVersions(projectId: string) {
  return useQuery({
    queryKey: qk.projects.divisionVersions(projectId),
    queryFn: async () => {
      const result = await client.GET("/projects/{projectId}/lesson-divisions/versions", {
        params: { path: { projectId } },
      });
      return unwrap(result).data;
    },
  });
}

export function useSaveDivision(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { content: DivisionContent; row_version: number }) => {
      const result = await client.PATCH("/projects/{projectId}/lesson-divisions/current", {
        params: { path: { projectId } },
        body: {
          content: input.content as unknown as Record<string, unknown>,
          row_version: input.row_version,
        },
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.division(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.divisionVersions(projectId) });
    },
  });
}

export function useGenerateDivision(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const result = await client.POST("/projects/{projectId}/lesson-divisions/runs", {
        params: {
          path: { projectId },
          header: { "Idempotency-Key": createIdempotencyKey("division") },
        },
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.detail(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.tasksRoot(projectId) });
    },
  });
}

export function useApproveDivision(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (versionId: string) => {
      const result = await client.POST("/projects/{projectId}/lesson-divisions/{versionId}/approve", {
        params: { path: { projectId, versionId } },
        body: {},
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.division(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.divisionVersions(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.lessons(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.detail(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.homeOverview });
    },
  });
}
