import { type QueryKey, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  getLessonIntroOptions,
  selectLessonIntroOption,
} from "@/features/intro-options/api/introOptionsApi";
import {
  getGenerationJob,
  listProjectGenerationJobsPage,
  type GenerationJobDto,
} from "@/features/jobs/api/jobsApi";
import {
  getProjectWorkflow,
  prepareIntroOptionGeneration,
  startNodeRun,
} from "@/features/workflow/api/workflowApi";
import { ApiError } from "@/shared/api/client";
import { useJobEvents } from "@/shared/api/useJobEvents";

const terminalJobStatuses = new Set<GenerationJobDto["status"]>([
  "succeeded",
  "failed",
  "cancelled",
]);

export function isIntroOptionsMissing(reason: unknown) {
  return reason instanceof ApiError && reason.code === "INTRO_OPTIONS_NOT_FOUND";
}

export function useIntroOptionsRuntime(lessonId?: string) {
  const queryKey = ["lessons", lessonId, "intro-options"] as const;
  const query = useQuery({
    enabled: Boolean(lessonId),
    queryFn: () => getLessonIntroOptions(lessonId ?? ""),
    queryKey,
    retry: (failureCount, error) => !isIntroOptionsMissing(error) && failureCount < 2,
  });
  const missing = isIntroOptionsMissing(query.error);
  return {
    data: missing ? undefined : query.data,
    error: missing ? undefined : query.error,
    missing,
    query,
    queryKey,
  };
}

export function useIntroOptionsJobRuntime(projectId?: string, lessonId?: string) {
  const [startedJobId, setStartedJobId] = useState<string>();
  const workflowQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => getProjectWorkflow(projectId ?? ""),
    queryKey: ["projects", projectId, "workflow"],
  });
  const jobsKey = ["tasks", projectId, "intro-options", lessonId] as const;
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
        (node) => node.id === job.node_run_id && node.node_key === "intro.generate_options",
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

export function useIntroOptionsGenerationMutation({
  jobsKey,
  lessonId,
  onStarted,
}: {
  jobsKey: QueryKey;
  lessonId?: string;
  onStarted: (jobId: string) => void;
}) {
  const queryClient = useQueryClient();
  const prepareIntentRef = useRef<string | undefined>(undefined);
  const startIntentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: async () => {
      if (!lessonId) throw new Error("LESSON_ID_MISSING");
      prepareIntentRef.current ??= crypto.randomUUID();
      startIntentRef.current ??= crypto.randomUUID();
      const node = await prepareIntroOptionGeneration({
        generationMode: "default_nine",
        idempotencyKey: prepareIntentRef.current,
        lessonId,
      });
      return startNodeRun({
        idempotencyKey: startIntentRef.current,
        nodeRunId: node.id,
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

type SelectionInput = {
  artifactVersionId: string;
  optionKey: string;
};

export function useIntroOptionSelectionMutation({
  lessonId,
  refetchOptions,
}: {
  lessonId?: string;
  refetchOptions: () => Promise<unknown>;
}) {
  const intentRef = useRef<(SelectionInput & { key: string }) | undefined>(undefined);
  return useMutation({
    mutationFn: ({ artifactVersionId, optionKey }: SelectionInput) => {
      if (!lessonId) throw new Error("LESSON_ID_MISSING");
      let intent = intentRef.current;
      if (
        !intent ||
        intent.artifactVersionId !== artifactVersionId ||
        intent.optionKey !== optionKey
      ) {
        intent = { artifactVersionId, key: crypto.randomUUID(), optionKey };
        intentRef.current = intent;
      }
      return selectLessonIntroOption({
        artifactVersionId,
        idempotencyKey: intent.key,
        lessonId,
        optionKey,
      });
    },
    onSuccess: async () => {
      intentRef.current = undefined;
      await refetchOptions();
    },
  });
}
