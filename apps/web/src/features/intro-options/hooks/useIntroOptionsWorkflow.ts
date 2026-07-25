import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  getArtifact,
  reviewArtifactVersion,
  saveArtifactDraft,
  submitArtifactVersion,
  type ArtifactDto,
} from "@/features/artifacts/api/artifactsApi";
import {
  getIntroOptionArtifact,
  getLessonIntroOptions,
  listIntroOptionGenerationJobs,
  prepareIntroOptionGeneration,
  selectLessonIntroOption,
  startIntroOptionQualityValidation,
  type GenerationJobDto,
} from "@/features/intro-options/api/introOptionsApi";
import { getGenerationJob } from "@/features/jobs/api/jobsApi";
import { startNodeRun } from "@/features/workflow/api/workflowApi";
import { useJobEvents } from "@/shared/api/useJobEvents";

const terminalJobStatuses = new Set<GenerationJobDto["status"]>([
  "succeeded",
  "failed",
  "cancelled",
]);

export function introOptionsArtifactKey(projectId?: string, lessonId?: string) {
  return ["projects", projectId, "lessons", lessonId, "intro-options", "artifact"] as const;
}

export function introOptionsPublicKey(lessonId?: string) {
  return ["lessons", lessonId, "intro-options"] as const;
}

export function introOptionsJobsKey(projectId?: string, lessonId?: string) {
  return ["tasks", projectId, "intro-options", lessonId] as const;
}

export function useIntroOptionsArtifactRuntime(projectId?: string, lessonId?: string) {
  const [qualityPendingVersionId, setQualityPendingVersionId] = useState<string>();
  const aggregateKey = useMemo(
    () => introOptionsArtifactKey(projectId, lessonId),
    [lessonId, projectId],
  );
  const aggregateQuery = useQuery({
    enabled: Boolean(projectId && lessonId),
    queryFn: () => getIntroOptionArtifact({ lessonId: lessonId ?? "", projectId: projectId ?? "" }),
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
    candidate.artifact_type === "intro_option_set" &&
    candidate.branch_key === "intro_options"
      ? candidate
      : undefined;
  const publicKey = useMemo(() => introOptionsPublicKey(lessonId), [lessonId]);
  const publicQuery = useQuery({
    enabled: Boolean(artifact && lessonId),
    queryFn: () => getLessonIntroOptions(lessonId ?? ""),
    queryKey: publicKey,
  });
  const qualityReport = aggregateQuery.data?.quality_report;

  useEffect(() => {
    if (qualityPendingVersionId === qualityReport?.artifact_version_id) {
      setQualityPendingVersionId(undefined);
    }
  }, [qualityPendingVersionId, qualityReport?.artifact_version_id]);

  const refetchArtifact = async () => {
    await aggregateQuery.refetch();
    if (summary?.id) await detailQuery.refetch();
    if (artifact) await publicQuery.refetch();
  };

  return {
    aggregateKey,
    aggregateQuery,
    artifact,
    detailQuery,
    etag: detailQuery.data?.etag,
    latestApproval: aggregateQuery.data?.latest_approval,
    publicKey,
    publicQuery,
    qualityPendingVersionId,
    qualityReport,
    refetchArtifact,
    setQualityPendingVersionId,
  };
}

export function useIntroOptionsJobRuntime(projectId?: string, lessonId?: string) {
  const queryClient = useQueryClient();
  const [startedJobId, setStartedJobId] = useState<string>();
  const jobsKey = useMemo(() => introOptionsJobsKey(projectId, lessonId), [lessonId, projectId]);
  const jobsQuery = useQuery({
    enabled: Boolean(projectId && lessonId),
    queryFn: () =>
      listIntroOptionGenerationJobs({ lessonId: lessonId ?? "", projectId: projectId ?? "" }),
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
    candidate.workflow_node_key === "intro.generate_options"
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
        queryKey: introOptionsArtifactKey(projectId, lessonId),
      }),
      queryClient.invalidateQueries({
        exact: true,
        queryKey: introOptionsPublicKey(lessonId),
      }),
    ]);
  }, [job, jobsKey, lessonId, projectId, queryClient]);

  return { job, jobQuery, jobsQuery, setStartedJobId };
}

export function useIntroOptionsGenerationMutation({
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
      const node = await prepareIntroOptionGeneration({
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

export function useSaveIntroOptionsDraftMutation(options: ArtifactMutationOptions) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: (content: Record<string, unknown>) => {
      const draft = options.artifact?.current_draft;
      if (!options.artifact || !draft || !options.etag) {
        throw new Error("INTRO_OPTIONS_DRAFT_MISSING");
      }
      intentRef.current ??= crypto.randomUUID();
      return saveArtifactDraft({
        artifactId: options.artifact.id,
        draftBranch: draft.draft_branch,
        etag: options.etag,
        idempotencyKey: intentRef.current,
        input: { content },
      });
    },
    onSuccess: async () => {
      intentRef.current = undefined;
      await options.refetchArtifact();
    },
  });
}

export function useSubmitIntroOptionsDraftMutation(options: ArtifactMutationOptions) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: () => {
      const draft = options.artifact?.current_draft;
      if (!options.artifact || !draft || !options.etag) {
        throw new Error("INTRO_OPTIONS_DRAFT_MISSING");
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
      await options.refetchArtifact();
    },
  });
}

export function useIntroOptionsQualityMutation({
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
        throw new Error("INTRO_OPTIONS_VERSION_MISSING");
      }
      intentRef.current ??= crypto.randomUUID();
      const accepted = await startIntroOptionQualityValidation({
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

export function useIntroOptionsApprovalMutation({
  artifact,
  qualityPassed,
  refetchArtifact,
}: ArtifactMutationOptions & { qualityPassed: boolean }) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: () => {
      const versionId = artifact?.current_submitted_version?.id;
      if (!versionId || !qualityPassed) throw new Error("INTRO_OPTIONS_QUALITY_REQUIRED");
      intentRef.current ??= crypto.randomUUID();
      return reviewArtifactVersion({
        artifactVersionId: versionId,
        idempotencyKey: intentRef.current,
        input: { action: "approve", comment: "三类九套课堂导入方案已审阅确认" },
      });
    },
    onSuccess: async () => {
      intentRef.current = undefined;
      await refetchArtifact();
    },
  });
}

export function useIntroOptionSelectionMutation({
  lessonId,
  refetchArtifact,
  selectableVersionId,
}: {
  lessonId?: string;
  refetchArtifact: () => Promise<unknown>;
  selectableVersionId?: string;
}) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: (optionKey: string) => {
      if (!lessonId || !selectableVersionId) throw new Error("INTRO_OPTIONS_APPROVAL_REQUIRED");
      intentRef.current ??= crypto.randomUUID();
      return selectLessonIntroOption({
        artifactVersionId: selectableVersionId,
        idempotencyKey: intentRef.current,
        lessonId,
        optionKey,
      });
    },
    onSuccess: async () => {
      intentRef.current = undefined;
      await refetchArtifact();
    },
  });
}
