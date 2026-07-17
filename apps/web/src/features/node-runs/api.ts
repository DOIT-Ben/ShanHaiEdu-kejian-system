import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function useNodeRunDetail(nodeRunId: string | null) {
  return useQuery({
    queryKey: qk.nodeRuns.detail(nodeRunId ?? "none"),
    enabled: Boolean(nodeRunId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/node-runs/{node_run_id}", {
          params: { path: { node_run_id: nodeRunId! } },
        }),
      );
      return result.data;
    },
    refetchInterval: (query) => {
      const status = query.state.data?.node_run.status;
      return status === "queued" || status === "running" || status === "cancel_requested" ? 2_500 : false;
    },
  });
}

export function usePromptPreview(nodeRunId: string | null) {
  return useQuery({
    queryKey: qk.nodeRuns.promptPreview(nodeRunId ?? "none"),
    enabled: Boolean(nodeRunId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/node-runs/{node_run_id}/prompt-preview", {
          params: { path: { node_run_id: nodeRunId! } },
        }),
      );
      return { preview: result.data, etag: result.etag };
    },
  });
}

export function useSavePrompt(nodeRunId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { etag: string; editablePrompt: string }) => {
      const result = unwrap(
        await client.PUT("/node-runs/{node_run_id}/prompt", {
          params: { path: { node_run_id: nodeRunId }, header: { "If-Match": input.etag } },
          body: { editable_prompt: input.editablePrompt },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.nodeRuns.promptPreview(nodeRunId) });
    },
  });
}

export function useStartNode(nodeRunId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input?: { promptRevisionId?: string }) => {
      const result = unwrap(
        await client.POST("/node-runs/{node_run_id}/start", {
          params: { path: { node_run_id: nodeRunId }, header: { "Idempotency-Key": createIdempotencyKey("node-start") } },
          body: input?.promptRevisionId ? { prompt_revision_id: input.promptRevisionId } : {},
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.nodeRuns.detail(nodeRunId) });
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
    },
  });
}

export function useNodeTransition(nodeRunId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      action: "skip" | "resume" | "keep_current_version" | "acknowledge_stale";
      reason?: string;
    }) => {
      const result = unwrap(
        await client.POST("/node-runs/{node_run_id}/transitions", {
          params: { path: { node_run_id: nodeRunId }, header: { "Idempotency-Key": createIdempotencyKey("transition") } },
          body: { action: input.action, ...(input.reason ? { reason: input.reason } : {}) },
        }),
      );
      return result.data;
    },
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: qk.nodeRuns.detail(nodeRunId) });
      if (run.lesson_id) {
        void queryClient.invalidateQueries({ queryKey: qk.lessons.nodeRuns(run.lesson_id) });
      }
    },
  });
}

export function useNodeResults(nodeRunId: string | null, itemKey?: string) {
  return useQuery({
    queryKey: qk.nodeRuns.results(nodeRunId ?? "none", itemKey),
    enabled: Boolean(nodeRunId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/node-runs/{node_run_id}/results", {
          params: {
            path: { node_run_id: nodeRunId! },
            query: itemKey ? { item_key: itemKey } : {},
          },
        }),
      );
      return result.data.items;
    },
  });
}

export function useArtifactVersion(versionId: string | null) {
  return useQuery({
    queryKey: qk.artifacts.version(versionId ?? "none"),
    enabled: Boolean(versionId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/artifact-versions/{artifact_version_id}", {
          params: { path: { artifact_version_id: versionId! } },
        }),
      );
      return { version: result.data, etag: result.etag };
    },
  });
}

export function useSaveArtifactContent(versionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { etag: string; content: Record<string, unknown> }) => {
      const result = unwrap(
        await client.PUT("/artifact-versions/{artifact_version_id}/content", {
          params: { path: { artifact_version_id: versionId }, header: { "If-Match": input.etag } },
          body: { content: input.content },
        }),
      );
      return { version: result.data, etag: result.etag };
    },
    onSuccess: (data) => {
      queryClient.setQueryData(qk.artifacts.version(versionId), data);
    },
  });
}

export function useApproveArtifact(versionId: string, nodeRunId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input?: {
      note?: string;
      acknowledgedWarningKeys?: string[];
      acknowledgementNote?: string;
    }) => {
      const result = unwrap(
        await client.POST("/artifact-versions/{artifact_version_id}/approve", {
          params: { path: { artifact_version_id: versionId }, header: { "Idempotency-Key": createIdempotencyKey("approve") } },
          body: {
            ...(input?.note ? { note: input.note } : {}),
            ...(input?.acknowledgedWarningKeys?.length
              ? { acknowledged_warning_keys: input.acknowledgedWarningKeys }
              : {}),
            ...(input?.acknowledgementNote ? { acknowledgement_note: input.acknowledgementNote } : {}),
          },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.artifacts.version(versionId) });
      if (nodeRunId) {
        void queryClient.invalidateQueries({ queryKey: qk.nodeRuns.detail(nodeRunId) });
      }
      void queryClient.invalidateQueries({ queryKey: ["lessons"] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
}

export function useRequestChanges(versionId: string, nodeRunId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { instruction: string; scopeKeys?: string[] }) => {
      const result = unwrap(
        await client.POST("/artifact-versions/{artifact_version_id}/request-changes", {
          params: { path: { artifact_version_id: versionId }, header: { "Idempotency-Key": createIdempotencyKey("request-changes") } },
          body: {
            instruction: input.instruction,
            ...(input.scopeKeys?.length ? { scope_keys: input.scopeKeys } : {}),
          },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      if (nodeRunId) {
        void queryClient.invalidateQueries({ queryKey: qk.nodeRuns.detail(nodeRunId) });
      }
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
    },
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (jobId: string) => {
      const result = unwrap(
        await client.POST("/generation-jobs/{job_id}/cancel", {
          params: { path: { job_id: jobId }, header: { "Idempotency-Key": createIdempotencyKey("cancel") } },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
      void queryClient.invalidateQueries({ queryKey: ["node-runs"] });
    },
  });
}

export function useRetryJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { jobId: string; itemKeys?: string[] }) => {
      const result = unwrap(
        await client.POST("/generation-jobs/{job_id}/retry", {
          params: { path: { job_id: input.jobId }, header: { "Idempotency-Key": createIdempotencyKey("retry") } },
          body: input.itemKeys?.length ? { item_keys: input.itemKeys } : {},
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
      void queryClient.invalidateQueries({ queryKey: ["node-runs"] });
      void queryClient.invalidateQueries({ queryKey: ["video-projects"] });
    },
  });
}
