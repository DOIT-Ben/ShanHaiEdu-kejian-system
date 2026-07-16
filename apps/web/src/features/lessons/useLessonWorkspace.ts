import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, qk, unwrap } from "@/shared/api";

export function useLessons(projectId: string) {
  return useQuery({
    queryKey: qk.projects.lessons(projectId),
    queryFn: async () => {
      const result = await client.GET("/projects/{projectId}/lessons", { params: { path: { projectId } } });
      return unwrap(result).data;
    },
  });
}

export function useLesson(lessonId: string) {
  return useQuery({
    queryKey: qk.lessons.detail(lessonId),
    queryFn: async () => {
      const result = await client.GET("/lessons/{lessonId}", { params: { path: { lessonId } } });
      return unwrap(result).data;
    },
  });
}

export function useLessonWorkspace(lessonId: string) {
  return useQuery({
    queryKey: qk.lessons.workspace(lessonId),
    queryFn: async () => {
      const result = await client.GET("/lessons/{lessonId}/workspace", { params: { path: { lessonId } } });
      return unwrap(result).data;
    },
  });
}

export function useNodeWorkspace(lessonId: string, nodeKey: string) {
  return useQuery({
    queryKey: qk.lessons.node(lessonId, nodeKey),
    queryFn: async () => {
      const result = await client.GET("/lessons/{lessonId}/nodes/{nodeKey}", {
        params: { path: { lessonId, nodeKey } },
      });
      return unwrap(result).data;
    },
  });
}

export function useUpdateNodeInputs(lessonId: string, nodeKey: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      input_values?: Record<string, unknown>;
      selected_asset_ids?: string[];
      row_version: number;
    }) => {
      const result = await client.PATCH("/lessons/{lessonId}/nodes/{nodeKey}/inputs", {
        params: { path: { lessonId, nodeKey } },
        body: {
          input_values: input.input_values ?? {},
          selected_asset_ids: input.selected_asset_ids,
          row_version: input.row_version,
        },
      });
      return unwrap(result).data;
    },
    onSuccess: (workspace) => {
      queryClient.setQueryData(qk.lessons.node(lessonId, nodeKey), workspace);
    },
  });
}

export function useSaveNodeDraft(lessonId: string, nodeKey: string) {
  return useMutation({
    mutationFn: async (input: { content: Record<string, unknown>; row_version: number }) => {
      const result = await client.PATCH("/lessons/{lessonId}/nodes/{nodeKey}/draft", {
        params: { path: { lessonId, nodeKey } },
        body: input,
      });
      return unwrap(result).data;
    },
  });
}

export type NodeTransitionAction = "skip" | "restore" | "pause" | "resume";

export function useNodeTransition(lessonId: string, nodeKey: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { action: NodeTransitionAction; reason?: string }) => {
      const result = await client.POST("/lessons/{lessonId}/nodes/{nodeKey}/transitions", {
        params: { path: { lessonId, nodeKey } },
        body: input,
      });
      return unwrap(result).data;
    },
    onSuccess: (workspace) => {
      queryClient.setQueryData(qk.lessons.node(lessonId, nodeKey), workspace);
      void queryClient.invalidateQueries({ queryKey: qk.lessons.workspace(lessonId) });
    },
  });
}
