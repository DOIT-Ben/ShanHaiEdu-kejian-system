import { type QueryKey, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  getArtifact,
  listProjectArtifactsPage,
  saveArtifactDraft,
  submitArtifactVersion,
  type ArtifactDto,
} from "@/features/artifacts/api/artifactsApi";
import {
  getGenerationJob,
  listProjectGenerationJobsPage,
  type GenerationJobDto,
} from "@/features/jobs/api/jobsApi";
import {
  getProjectWorkflow,
  prepareLessonPlanGeneration,
  startNodeRun,
} from "@/features/workflow/api/workflowApi";
import { useJobEvents } from "@/shared/api/useJobEvents";

const terminalJobStatuses = new Set<GenerationJobDto["status"]>([
  "succeeded",
  "failed",
  "cancelled",
]);

type ArtifactDetail = Awaited<ReturnType<typeof getArtifact>>;

export function useLessonPlanArtifactRuntime(projectId?: string, lessonId?: string) {
  const listKey = ["projects", projectId, "artifacts", "lesson_plan", lessonId] as const;
  const listQuery = useQuery({
    enabled: Boolean(projectId && lessonId),
    queryFn: () =>
      listProjectArtifactsPage({
        artifactType: "lesson_plan",
        lessonId: lessonId ?? "",
        limit: 100,
        projectId: projectId ?? "",
      }),
    queryKey: listKey,
  });
  const summary = listQuery.data?.items.find(
    (artifact) =>
      artifact.project_id === projectId &&
      artifact.lesson_unit_id === lessonId &&
      artifact.artifact_type === "lesson_plan",
  );
  const detailKey = ["artifacts", summary?.id] as const;
  const detailQuery = useQuery({
    enabled: Boolean(summary?.id),
    queryFn: () => getArtifact(summary?.id ?? ""),
    queryKey: detailKey,
  });
  const candidate = detailQuery.data?.artifact;
  const artifact =
    candidate &&
    candidate.id === summary?.id &&
    candidate.project_id === projectId &&
    candidate.lesson_unit_id === lessonId &&
    candidate.artifact_type === "lesson_plan"
      ? candidate
      : undefined;
  return { artifact, detailKey, detailQuery, etag: detailQuery.data?.etag, listQuery };
}

export function useLessonPlanJobRuntime(projectId?: string, lessonId?: string) {
  const [startedJobId, setStartedJobId] = useState<string>();
  const workflowQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => getProjectWorkflow(projectId ?? ""),
    queryKey: ["projects", projectId, "workflow"],
  });
  const jobsKey = ["tasks", projectId, "lesson-plan", lessonId] as const;
  const jobsQuery = useQuery({
    enabled: Boolean(projectId && lessonId),
    queryFn: () =>
      listProjectGenerationJobsPage({
        lessonId: lessonId ?? "",
        limit: 100,
        projectId: projectId ?? "",
      }),
    queryKey: jobsKey,
  });
  const recoveredJob = jobsQuery.data?.items.find(
    (job) =>
      job.project_id === projectId &&
      job.lesson_unit_id === lessonId &&
      job.job_type === "workflow.node" &&
      workflowQuery.data?.node_runs.some(
        (node) => node.id === job.node_run_id && node.node_key === "lesson_plan.generate",
      ),
  );
  const activeJobId = startedJobId ?? recoveredJob?.id;
  const jobQuery = useQuery({
    enabled: Boolean(activeJobId),
    placeholderData: recoveredJob,
    queryFn: () => getGenerationJob(activeJobId ?? ""),
    queryKey: ["generation-jobs", activeJobId],
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && terminalJobStatuses.has(status) ? false : 5_000;
    },
  });
  const candidate = jobQuery.data;
  const job =
    candidate && candidate.project_id === projectId && candidate.lesson_unit_id === lessonId
      ? candidate
      : undefined;
  const live = Boolean(job && !terminalJobStatuses.has(job.status));
  useJobEvents(live ? activeJobId : undefined, live ? projectId : undefined);
  return { job, jobQuery, jobsKey, jobsQuery, setStartedJobId, workflowQuery };
}

type GenerationMutationOptions = {
  jobsKey: QueryKey;
  lessonId?: string;
  onStarted: (jobId: string) => void;
};

export function useLessonPlanGenerationMutation({
  jobsKey,
  lessonId,
  onStarted,
}: GenerationMutationOptions) {
  const queryClient = useQueryClient();
  const prepareIntentRef = useRef<string | undefined>(undefined);
  const startIntentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: async (userRevision: string) => {
      if (!lessonId) throw new Error("LESSON_ID_MISSING");
      prepareIntentRef.current ??= crypto.randomUUID();
      startIntentRef.current ??= crypto.randomUUID();
      const node = await prepareLessonPlanGeneration({
        idempotencyKey: prepareIntentRef.current,
        lessonId,
      });
      return startNodeRun({
        idempotencyKey: startIntentRef.current,
        nodeRunId: node.id,
        userRevision: userRevision.trim() || undefined,
      });
    },
    onSuccess: (accepted) => {
      prepareIntentRef.current = undefined;
      startIntentRef.current = undefined;
      onStarted(accepted.job_id);
      void queryClient.invalidateQueries({ exact: true, queryKey: jobsKey });
    },
  });
}

type SaveDraftMutationOptions = {
  artifact?: ArtifactDto;
  detailKey: QueryKey;
  etag?: string;
};

export function useSaveLessonPlanDraftMutation({
  artifact,
  detailKey,
  etag,
}: SaveDraftMutationOptions) {
  const queryClient = useQueryClient();
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: (content: Record<string, unknown>) => {
      const draft = artifact?.current_draft;
      if (!artifact || !draft || !etag) throw new Error("LESSON_PLAN_DRAFT_MISSING");
      intentRef.current ??= crypto.randomUUID();
      return saveArtifactDraft({
        artifactId: artifact.id,
        draftBranch: draft.draft_branch,
        etag,
        idempotencyKey: intentRef.current,
        input: { content },
      });
    },
    onSuccess: ({ draft, etag: nextEtag }) => {
      intentRef.current = undefined;
      queryClient.setQueryData<ArtifactDetail>(detailKey, (current) =>
        current
          ? {
              artifact: { ...current.artifact, current_draft: draft },
              etag: nextEtag ?? current.etag,
            }
          : current,
      );
    },
  });
}

type SubmitDraftMutationOptions = {
  artifact?: ArtifactDto;
  etag?: string;
  refetchArtifact: () => Promise<unknown>;
};

export function useSubmitLessonPlanDraftMutation({
  artifact,
  etag,
  refetchArtifact,
}: SubmitDraftMutationOptions) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: () => {
      const draft = artifact?.current_draft;
      if (!artifact || !draft || !etag) throw new Error("LESSON_PLAN_DRAFT_MISSING");
      intentRef.current ??= crypto.randomUUID();
      return submitArtifactVersion({
        artifactId: artifact.id,
        draftBranch: draft.draft_branch,
        etag,
        idempotencyKey: intentRef.current,
      });
    },
    onSuccess: async () => {
      intentRef.current = undefined;
      await refetchArtifact();
    },
  });
}
