import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useRef } from "react";
import { cancelGenerationJob } from "@/features/jobs/api/jobsApi";
import {
  adoptVideoResult,
  getVideoGoldenSlice,
  saveVideoAdoption,
  startVideoGeneration,
} from "@/features/video-golden-slice/api/videoGoldenSliceApi";
import { useJobEvents } from "@/shared/api/useJobEvents";

const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);

export function videoGoldenSliceKey(projectId?: string, lessonId?: string) {
  return ["projects", projectId, "lessons", lessonId, "video-golden-slice"] as const;
}

export function useVideoGoldenSlice(projectId?: string, lessonId?: string) {
  const queryClient = useQueryClient();
  const queryKey = useMemo(() => videoGoldenSliceKey(projectId, lessonId), [lessonId, projectId]);
  const query = useQuery({
    enabled: Boolean(projectId && lessonId),
    queryFn: () => getVideoGoldenSlice({ lessonId: lessonId ?? "", projectId: projectId ?? "" }),
    queryKey,
    refetchInterval: (current) => {
      const status = current.state.data?.job?.status;
      return status && !terminalStatuses.has(status) ? 2_500 : false;
    },
  });
  const job = query.data?.job;
  const live = Boolean(job && !terminalStatuses.has(job.status));
  useJobEvents(live ? job?.id : undefined, live ? projectId : undefined);

  const invalidate = () => queryClient.invalidateQueries({ exact: true, queryKey });
  const startIntent = useRef<string | undefined>(undefined);
  const adoptIntent = useRef<string | undefined>(undefined);
  const saveIntent = useRef<string | undefined>(undefined);
  const cancelIntent = useRef<string | undefined>(undefined);

  const startMutation = useMutation({
    mutationFn: async () => {
      const keyframeId = query.data?.keyframe_file_asset_version_id;
      if (!projectId || !lessonId || !keyframeId) throw new Error("VIDEO_INPUTS_MISSING");
      startIntent.current ??= crypto.randomUUID();
      return startVideoGeneration({
        idempotencyKey: startIntent.current,
        keyframeFileAssetVersionId: keyframeId,
        lessonId,
        projectId,
      });
    },
    onSuccess: async () => {
      startIntent.current = undefined;
      await invalidate();
    },
  });
  const adoptMutation = useMutation({
    mutationFn: async (resultId: string) => {
      if (!projectId || !lessonId) throw new Error("VIDEO_CONTEXT_MISSING");
      adoptIntent.current ??= crypto.randomUUID();
      return adoptVideoResult({
        idempotencyKey: adoptIntent.current,
        lessonId,
        projectId,
        resultId,
      });
    },
    onSuccess: async () => {
      adoptIntent.current = undefined;
      await invalidate();
    },
  });
  const saveMutation = useMutation({
    mutationFn: async (adoptionId: string) => {
      if (!projectId || !lessonId) throw new Error("VIDEO_CONTEXT_MISSING");
      saveIntent.current ??= crypto.randomUUID();
      return saveVideoAdoption({
        adoptionId,
        idempotencyKey: saveIntent.current,
        lessonId,
        projectId,
      });
    },
    onSuccess: async () => {
      saveIntent.current = undefined;
      await invalidate();
    },
  });
  const cancelMutation = useMutation({
    mutationFn: async () => {
      if (!job) throw new Error("VIDEO_JOB_MISSING");
      cancelIntent.current ??= crypto.randomUUID();
      return cancelGenerationJob({ idempotencyKey: cancelIntent.current, jobId: job.id });
    },
    onSuccess: async () => {
      cancelIntent.current = undefined;
      await invalidate();
    },
  });

  return { adoptMutation, cancelMutation, query, saveMutation, startMutation };
}
