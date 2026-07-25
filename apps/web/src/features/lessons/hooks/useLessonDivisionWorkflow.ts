import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  getArtifact,
  getLessonDivisionArtifact,
  reviewArtifactVersion,
  saveArtifactDraft,
  startLessonDivisionQualityValidation,
  submitArtifactVersion,
  type ArtifactDto,
} from "@/features/artifacts/api/artifactsApi";
import {
  getGenerationJob,
  listLessonDivisionGenerationJobs,
  type GenerationJobDto,
} from "@/features/jobs/api/jobsApi";
import { prepareLessonDivision, startNodeRun } from "@/features/workflow/api/workflowApi";
import { useJobEvents } from "@/shared/api/useJobEvents";

const terminalJobStatuses = new Set<GenerationJobDto["status"]>([
  "succeeded",
  "failed",
  "cancelled",
]);

export function lessonDivisionArtifactKey(projectId?: string) {
  return ["projects", projectId, "lesson-division", "artifact"] as const;
}

export function lessonDivisionJobsKey(projectId?: string) {
  return ["tasks", projectId, "lesson-division"] as const;
}

export function useLessonDivisionArtifactRuntime(projectId?: string) {
  const [qualityPendingVersionId, setQualityPendingVersionId] = useState<string>();
  const aggregateKey = useMemo(() => lessonDivisionArtifactKey(projectId), [projectId]);
  const aggregateQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => getLessonDivisionArtifact(projectId ?? ""),
    queryKey: aggregateKey,
    refetchInterval: (query) =>
      qualityPendingVersionId &&
      query.state.data?.quality_report?.artifact_version_id !== qualityPendingVersionId
        ? 2_000
        : false,
  });
  const summary = aggregateQuery.data?.artifact;
  const detailQuery = useQuery({
    enabled: Boolean(summary?.id),
    queryFn: () => getArtifact(summary?.id ?? ""),
    queryKey: ["artifacts", summary?.id],
  });
  const candidate = detailQuery.data?.artifact;
  const artifact =
    candidate &&
    candidate.id === summary?.id &&
    candidate.project_id === projectId &&
    candidate.lesson_unit_id === null &&
    candidate.artifact_type === "lesson_division"
      ? candidate
      : undefined;
  const qualityReport = aggregateQuery.data?.quality_report;
  useEffect(() => {
    if (qualityPendingVersionId === qualityReport?.artifact_version_id) {
      setQualityPendingVersionId(undefined);
    }
  }, [qualityPendingVersionId, qualityReport?.artifact_version_id]);
  const refetch = async () => {
    await aggregateQuery.refetch();
    if (summary?.id) await detailQuery.refetch();
  };
  return {
    aggregateQuery,
    artifact,
    detailQuery,
    etag: detailQuery.data?.etag,
    latestApproval: aggregateQuery.data?.latest_approval,
    qualityPendingVersionId,
    qualityReport,
    refetch,
    setQualityPendingVersionId,
  };
}

export function useLessonDivisionJobRuntime(projectId?: string) {
  const queryClient = useQueryClient();
  const [startedJobId, setStartedJobId] = useState<string>();
  const jobsKey = useMemo(() => lessonDivisionJobsKey(projectId), [projectId]);
  const jobsQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => listLessonDivisionGenerationJobs(projectId ?? ""),
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
    candidate.lesson_unit_id === null &&
    candidate.workflow_node_key === "lesson.division.generate"
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
        queryKey: lessonDivisionArtifactKey(projectId),
      }),
    ]);
  }, [job, jobsKey, projectId, queryClient]);
  return { job, jobQuery, jobsQuery, setStartedJobId };
}

export function useLessonDivisionGenerationMutation({
  onStarted,
  projectId,
}: {
  onStarted: (jobId: string) => void;
  projectId?: string;
}) {
  const prepareIntentRef = useRef<string | undefined>(undefined);
  const startIntentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: async (materialScopeArtifactVersionId: string) => {
      if (!projectId) throw new Error("PROJECT_ID_MISSING");
      prepareIntentRef.current ??= crypto.randomUUID();
      startIntentRef.current ??= crypto.randomUUID();
      const node = await prepareLessonDivision({
        idempotencyKey: prepareIntentRef.current,
        materialScopeArtifactVersionId,
        projectId,
      });
      return startNodeRun({ idempotencyKey: startIntentRef.current, nodeRunId: node.id });
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
  refetch: () => Promise<unknown>;
};

export function useSaveLessonDivisionDraftMutation({
  artifact,
  etag,
  refetch,
}: ArtifactMutationOptions) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: (content: Record<string, unknown>) => {
      const draft = artifact?.current_draft;
      if (!artifact || !draft || !etag) throw new Error("LESSON_DIVISION_DRAFT_MISSING");
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
      await refetch();
    },
  });
}

export function useSubmitLessonDivisionDraftMutation(options: ArtifactMutationOptions) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: () => {
      const draft = options.artifact?.current_draft;
      if (!options.artifact || !draft || !options.etag) {
        throw new Error("LESSON_DIVISION_DRAFT_MISSING");
      }
      intentRef.current ??= crypto.randomUUID();
      return submitArtifactVersion({
        artifactId: options.artifact.id,
        draftBranch: draft.draft_branch,
        etag: options.etag,
        idempotencyKey: intentRef.current,
      });
    },
    onSuccess: async () => {
      intentRef.current = undefined;
      await options.refetch();
    },
  });
}

export function useLessonDivisionQualityMutation({
  artifact,
  onRequested,
  projectId,
  refetch,
}: ArtifactMutationOptions & {
  onRequested: (artifactVersionId: string) => void;
  projectId?: string;
}) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: async (versionId: string) => {
      if (!projectId || artifact?.current_submitted_version?.id !== versionId) {
        throw new Error("LESSON_DIVISION_VERSION_MISSING");
      }
      intentRef.current ??= crypto.randomUUID();
      await startLessonDivisionQualityValidation({
        artifactVersionId: versionId,
        idempotencyKey: intentRef.current,
        projectId,
      });
      return versionId;
    },
    onSuccess: async (versionId) => {
      intentRef.current = undefined;
      onRequested(versionId);
      await refetch();
    },
  });
}

export function useLessonDivisionApprovalMutation({
  artifact,
  qualityPassed,
  refetch,
}: ArtifactMutationOptions & { qualityPassed: boolean }) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: () => {
      const versionId = artifact?.current_submitted_version?.id;
      if (!versionId || !qualityPassed) throw new Error("LESSON_DIVISION_QUALITY_REQUIRED");
      intentRef.current ??= crypto.randomUUID();
      return reviewArtifactVersion({
        artifactVersionId: versionId,
        idempotencyKey: intentRef.current,
        input: { action: "approve", comment: "课时划分已审阅确认" },
      });
    },
    onSuccess: async () => {
      intentRef.current = undefined;
      await refetch();
    },
  });
}
