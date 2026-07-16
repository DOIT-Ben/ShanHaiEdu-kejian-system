import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, qk, unwrap } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export type ModelProfile = "recommended" | "quality" | "economy" | "fast_draft" | "advanced";
export type NodeItemActionType =
  | "revise"
  | "regenerate"
  | "approve"
  | "lock_creative_redo_anchor"
  | "duplicate_as_custom"
  | "retry_clip"
  | "approve_clip"
  | "replace_image";

export function useModelOptions(lessonId: string, nodeKey: string) {
  return useQuery({
    queryKey: qk.lessons.modelOptions(lessonId, nodeKey),
    queryFn: async () => {
      const result = await client.GET("/lessons/{lessonId}/nodes/{nodeKey}/model-options", {
        params: { path: { lessonId, nodeKey } },
      });
      return unwrap(result).data;
    },
    staleTime: 10 * 60 * 1000,
  });
}

export function useCreatePromptDraft(lessonId: string, nodeKey: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      input_values?: Record<string, unknown>;
      revision_instruction?: string;
      base_prompt_version_id?: string;
      edited_prompt?: string;
      reset_to_default?: boolean;
    }) => {
      const result = await client.POST("/lessons/{lessonId}/nodes/{nodeKey}/prompt-drafts", {
        params: { path: { lessonId, nodeKey } },
        body: {
          input_values: input.input_values ?? {},
          revision_instruction: input.revision_instruction,
          base_prompt_version_id: input.base_prompt_version_id,
          edited_prompt: input.edited_prompt,
          reset_to_default: input.reset_to_default,
        },
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.lessons.node(lessonId, nodeKey) });
    },
  });
}

export function useCostEstimate(lessonId: string, nodeKey: string) {
  return useMutation({
    mutationFn: async (input: {
      promptVersionId: string;
      modelProfile: ModelProfile;
      modelId?: string | null;
      parameters?: Record<string, unknown>;
    }) => {
      const result = await client.POST("/lessons/{lessonId}/nodes/{nodeKey}/cost-estimate", {
        params: { path: { lessonId, nodeKey } },
        body: {
          prompt_version_id: input.promptVersionId,
          model_profile: input.modelProfile,
          model_id: input.modelId,
          parameters: input.parameters ?? {},
        },
      });
      return unwrap(result).data;
    },
  });
}

export function useCreateBudgetAuthorization(lessonId: string, nodeKey: string) {
  return useMutation({
    mutationFn: async (input: { estimated_max_minor_units: number; reason: string }) => {
      const result = await client.POST("/lessons/{lessonId}/nodes/{nodeKey}/budget-authorizations", {
        params: { path: { lessonId, nodeKey } },
        body: input,
      });
      return unwrap(result).data;
    },
  });
}

export function useStartNodeRun(lessonId: string, nodeKey: string, projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      promptVersionId: string;
      modelProfile: ModelProfile;
      modelId?: string | null;
      parameters?: Record<string, unknown>;
      budgetAuthorizationId?: string | null;
    }) => {
      const result = await client.POST("/lessons/{lessonId}/nodes/{nodeKey}/runs", {
        params: {
          path: { lessonId, nodeKey },
          header: { "Idempotency-Key": createIdempotencyKey("run") },
        },
        body: {
          prompt_version_id: input.promptVersionId,
          model_profile: input.modelProfile,
          model_id: input.modelId,
          parameters: input.parameters ?? {},
          budget_authorization_id: input.budgetAuthorizationId,
        },
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.lessons.node(lessonId, nodeKey) });
      void queryClient.invalidateQueries({ queryKey: qk.lessons.workspace(lessonId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.tasksRoot(projectId) });
    },
  });
}

export function useNodeItemAction(lessonId: string, nodeKey: string, projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      itemId: string;
      action: NodeItemActionType;
      instruction?: string;
      payload?: Record<string, unknown>;
    }) => {
      const result = await client.POST("/lessons/{lessonId}/nodes/{nodeKey}/items/{itemId}/actions", {
        params: {
          path: { lessonId, nodeKey, itemId: input.itemId },
          header: { "Idempotency-Key": createIdempotencyKey("item") },
        },
        body: { action: input.action, instruction: input.instruction, payload: input.payload },
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.lessons.node(lessonId, nodeKey) });
      void queryClient.invalidateQueries({ queryKey: qk.lessons.workspace(lessonId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.tasksRoot(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.assetsRoot(projectId) });
    },
  });
}

export function useCreateEditedVersion(lessonId: string, nodeKey: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { content: Record<string, unknown>; base_version_id?: string }) => {
      const result = await client.POST("/lessons/{lessonId}/nodes/{nodeKey}/artifact-versions", {
        params: { path: { lessonId, nodeKey } },
        body: input,
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.lessons.node(lessonId, nodeKey) });
      void queryClient.invalidateQueries({ queryKey: qk.lessons.workspace(lessonId) });
    },
  });
}
