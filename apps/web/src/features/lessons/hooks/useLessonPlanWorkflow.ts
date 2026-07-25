import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  getArtifact,
  getLessonPlanArtifact,
  reviewArtifactVersion,
  saveArtifactDraft,
  startLessonPlanQualityValidation,
  submitArtifactVersion,
  type ArtifactDto,
} from "@/features/artifacts/api/artifactsApi";
import {
  getGenerationJob,
  listLessonPlanGenerationJobs,
  type GenerationJobDto,
} from "@/features/jobs/api/jobsApi";
import { prepareLessonPlanGeneration, startNodeRun } from "@/features/workflow/api/workflowApi";
import { useJobEvents } from "@/shared/api/useJobEvents";

const terminalJobStatuses = new Set<GenerationJobDto["status"]>([
  "succeeded",
  "failed",
  "cancelled",
]);

export function lessonPlanArtifactKey(projectId?: string, lessonId?: string) {
  return ["projects", projectId, "lessons", lessonId, "lesson-plan", "artifact"] as const;
}

export function lessonPlanJobsKey(projectId?: string, lessonId?: string) {
  return ["tasks", projectId, "lesson-plan", lessonId] as const;
}

export function useLessonPlanArtifactRuntime(projectId?: string, lessonId?: string) {
  const [qualityPendingVersionId, setQualityPendingVersionId] = useState<string>();
  const aggregateKey = useMemo(
    () => lessonPlanArtifactKey(projectId, lessonId),
    [lessonId, projectId],
  );
  const aggregateQuery = useQuery({
    enabled: Boolean(projectId && lessonId),
    queryFn: () => getLessonPlanArtifact({ lessonId: lessonId ?? "", projectId: projectId ?? "" }),
    queryKey: aggregateKey,
    refetchInterval: (query) =>
      qualityPendingVersionId &&
      query.state.data?.quality_report?.artifact_version_id !== qualityPendingVersionId
        ? 2_000
        : false,
  });
  const summary = aggregateQuery.data?.artifact;
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
  const qualityReport = aggregateQuery.data?.quality_report;
  const latestApproval = aggregateQuery.data?.latest_approval;

  useEffect(() => {
    if (qualityPendingVersionId === qualityReport?.artifact_version_id) {
      setQualityPendingVersionId(undefined);
    }
  }, [qualityPendingVersionId, qualityReport?.artifact_version_id]);

  const refetchArtifact = async () => {
    await aggregateQuery.refetch();
    if (summary?.id) await detailQuery.refetch();
  };

  return {
    aggregateKey,
    aggregateQuery,
    artifact,
    detailKey,
    detailQuery,
    etag: detailQuery.data?.etag,
    latestApproval,
    qualityPendingVersionId,
    qualityReport,
    refetchArtifact,
    setQualityPendingVersionId,
  };
}

export function useLessonPlanJobRuntime(projectId?: string, lessonId?: string) {
  const queryClient = useQueryClient();
  const [startedJobId, setStartedJobId] = useState<string>();
  const jobsKey = useMemo(() => lessonPlanJobsKey(projectId, lessonId), [lessonId, projectId]);
  const jobsQuery = useQuery({
    enabled: Boolean(projectId && lessonId),
    queryFn: () =>
      listLessonPlanGenerationJobs({
        lessonId: lessonId ?? "",
        projectId: projectId ?? "",
      }),
    queryKey: jobsKey,
  });
  const recoveredJob = jobsQuery.data?.[0];
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
    candidate &&
    candidate.project_id === projectId &&
    candidate.lesson_unit_id === lessonId &&
    candidate.workflow_node_key === "lesson_plan.generate"
      ? candidate
      : undefined;
  const live = Boolean(job && !terminalJobStatuses.has(job.status));
  useJobEvents(live ? activeJobId : undefined, live ? projectId : undefined);

  useEffect(() => {
    if (!job || !terminalJobStatuses.has(job.status)) return;
    void Promise.all([
      queryClient.invalidateQueries({ exact: true, queryKey: jobsKey }),
      queryClient.invalidateQueries({
        exact: true,
        queryKey: lessonPlanArtifactKey(projectId, lessonId),
      }),
    ]);
  }, [job, jobsKey, lessonId, projectId, queryClient]);

  return { job, jobQuery, jobsKey, jobsQuery, setStartedJobId };
}

export function useLessonPlanGenerationMutation({
  lessonId,
  onStarted,
}: {
  lessonId?: string;
  onStarted: (jobId: string) => void;
}) {
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
    },
  });
}

type ArtifactMutationOptions = {
  artifact?: ArtifactDto;
  etag?: string;
  refetchArtifact: () => Promise<unknown>;
};

export function useSaveLessonPlanDraftMutation({
  artifact,
  etag,
  refetchArtifact,
}: ArtifactMutationOptions) {
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
    onSuccess: async () => {
      intentRef.current = undefined;
      await refetchArtifact();
    },
  });
}

export function useSubmitLessonPlanDraftMutation({
  artifact,
  etag,
  refetchArtifact,
}: ArtifactMutationOptions) {
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

export function useLessonPlanQualityMutation({
  artifact,
  lessonId,
  onRequested,
  refetchArtifact,
}: ArtifactMutationOptions & {
  lessonId?: string;
  onRequested: (artifactVersionId: string) => void;
}) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: async (versionId: string) => {
      if (!lessonId || artifact?.current_submitted_version?.id !== versionId) {
        throw new Error("LESSON_PLAN_VERSION_MISSING");
      }
      intentRef.current ??= crypto.randomUUID();
      const accepted = await startLessonPlanQualityValidation({
        artifactVersionId: versionId,
        idempotencyKey: intentRef.current,
        lessonId,
      });
      return { accepted, versionId };
    },
    onSuccess: async ({ versionId }) => {
      intentRef.current = undefined;
      onRequested(versionId);
      await refetchArtifact();
    },
  });
}

export function useLessonPlanApprovalMutation({
  artifact,
  qualityPassed,
  refetchArtifact,
}: ArtifactMutationOptions & { qualityPassed: boolean }) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: () => {
      const versionId = artifact?.current_submitted_version?.id;
      if (!versionId || !qualityPassed) throw new Error("LESSON_PLAN_QUALITY_REQUIRED");
      intentRef.current ??= crypto.randomUUID();
      return reviewArtifactVersion({
        artifactVersionId: versionId,
        idempotencyKey: intentRef.current,
        input: { action: "approve", comment: "十二部分教案已审阅确认" },
      });
    },
    onSuccess: async () => {
      intentRef.current = undefined;
      await refetchArtifact();
    },
  });
}
