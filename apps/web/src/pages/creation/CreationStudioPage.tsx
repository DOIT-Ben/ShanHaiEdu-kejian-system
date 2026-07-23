import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { CreationAdvancedPanel } from "@/features/creation-studio/CreationAdvancedPanel";
import { CreationComposer } from "@/features/creation-studio/CreationComposer";
import {
  CreationResultUnavailableNotice,
  CreationSessionBoundaryNotice,
} from "@/features/creation-studio/CreationSessionOutcome";
import { CreationSetupPanel } from "@/features/creation-studio/CreationSetupPanel";
import { PromptReviewDialog } from "@/features/creation-studio/PromptReviewDialog";
import {
  createCreationBatch,
  generateCreationItem,
  saveCreationPromptVersion,
} from "@/features/creation-studio/api/creationApi";
import type { CreationStage } from "@/features/creation-studio/model";
import { studioRegistry } from "@/features/creation-studio/registry";
import {
  CreationItemUnavailableError,
  type GenerationIntent,
  generationProfile,
  initialAdvancedSettings,
  initialCreationSettings,
  studioTypeByPath,
  terminalCreationJobStatuses,
} from "@/features/creation-studio/runtimeState";
import { cancelGenerationJob, getGenerationJob } from "@/features/jobs/api/jobsApi";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { useJobEvents } from "@/shared/api/useJobEvents";

export function CreationStudioPage() {
  const { studioPath } = useParams();
  const type = studioPath ? studioTypeByPath[studioPath] : undefined;
  const config = type ? studioRegistry[type] : undefined;
  const queryClient = useQueryClient();
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [advancedSettings, setAdvancedSettings] = useState(initialAdvancedSettings);
  const [description, setDescription] = useState("");
  const [promptOpen, setPromptOpen] = useState(false);
  const [settings, setSettings] = useState(() => ({
    ...initialCreationSettings,
    ratio: type === "image" ? "4:3" : "16:9",
  }));
  const [itemId, setItemId] = useState<string>();
  const [jobId, setJobId] = useState<string>();
  const intentRef = useRef<GenerationIntent | undefined>(undefined);
  const cancelKeyRef = useRef<string | undefined>(undefined);

  const jobKey = ["generation-jobs", jobId] as const;
  const jobQuery = useQuery({
    enabled: Boolean(jobId),
    queryFn: () => getGenerationJob(jobId ?? ""),
    queryKey: jobKey,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && terminalCreationJobStatuses.has(status) ? false : 5_000;
    },
  });
  const job = jobQuery.data;
  const live = Boolean(jobId && job && !terminalCreationJobStatuses.has(job.status));
  useJobEvents(live && jobId ? jobId : undefined);

  const createMutation = useMutation({
    mutationFn: async () => {
      if (!type || !config) throw new Error("CREATION_STUDIO_NOT_FOUND");
      const fingerprint = JSON.stringify({ advancedSettings, description, settings, type });
      if (!intentRef.current || intentRef.current.fingerprint !== fingerprint) {
        intentRef.current = {
          batchKey: crypto.randomUUID(),
          fingerprint,
          generateKey: crypto.randomUUID(),
          promptKey: crypto.randomUUID(),
        };
      }
      const intent = intentRef.current;
      let currentItemId = itemId;
      if (!currentItemId) {
        const batch = await createCreationBatch({
          idempotencyKey: intent.batchKey,
          input: { source_kind: "standalone", studio_type: type, title: config.entryTitle },
        });
        currentItemId = batch.items[0]?.id;
        if (!currentItemId) throw new CreationItemUnavailableError();
        setItemId(currentItemId);
      }
      const prompt = await saveCreationPromptVersion({
        idempotencyKey: intent.promptKey,
        input: {
          business_prompt: description.trim(),
          generation_profile: generationProfile(settings.model),
          output_spec: {
            composition: advancedSettings.composition,
            duration_seconds: type === "video" ? Number(settings.duration) : undefined,
            negative_prompt: advancedSettings.negativePrompt,
            ratio: settings.ratio,
            reference_strength: advancedSettings.referenceStrength,
            style: settings.style,
            studio_type: type,
          },
          reference_asset_version_ids: [],
        },
        itemId: currentItemId,
      });
      const accepted = await generateCreationItem({
        idempotencyKey: intent.generateKey,
        input: {
          candidate_count: Math.max(1, Number.parseInt(settings.candidateCount, 10) || 1),
          prompt_version_id: prompt.id,
        },
        itemId: currentItemId,
      });
      return accepted.job_id;
    },
    onSuccess: (nextJobId) => {
      intentRef.current = undefined;
      setJobId(nextJobId);
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => {
      if (!jobId) throw new Error("GENERATION_JOB_NOT_FOUND");
      const idempotencyKey = cancelKeyRef.current ?? crypto.randomUUID();
      cancelKeyRef.current = idempotencyKey;
      return cancelGenerationJob({ idempotencyKey, jobId });
    },
    onSuccess: (cancelledJob) => {
      cancelKeyRef.current = undefined;
      queryClient.setQueryData(jobKey, cancelledJob);
    },
  });
  const resetCancelMutation = cancelMutation.reset;

  useEffect(() => {
    if (!job?.status || !terminalCreationJobStatuses.has(job.status)) return;
    cancelKeyRef.current = undefined;
    resetCancelMutation();
  }, [job?.status, resetCancelMutation]);

  const stage = useMemo<CreationStage>(() => {
    if (createMutation.isPending) return "queued";
    if (createMutation.isError) return "failed";
    if (jobId && !job) return "queued";
    if (job?.status === "failed") return "failed";
    if (job?.status === "cancelled") return "cancelled";
    if (job?.status === "created" || job?.status === "queued") return "queued";
    if (job?.status === "running" || job?.status === "cancel_requested") return "running";
    if (job?.status === "succeeded") return "ready";
    return "draft";
  }, [createMutation.isError, createMutation.isPending, job, jobId]);

  if (!type || !config) return <Navigate replace to="/app/creation" />;

  const writeReady = isCsrfTokenAvailable();
  const errorMessage = createMutation.isError
    ? createMutation.error instanceof CreationItemUnavailableError
      ? "独立创作暂时无法生成作品，请稍后再试。"
      : runtimeErrorMessage(createMutation.error, "创作任务没有开始，请检查网络后重试。")
    : jobQuery.isError
      ? runtimeErrorMessage(jobQuery.error, "任务状态暂时无法读取，请刷新后重试。")
      : cancelMutation.isError
        ? runtimeErrorMessage(cancelMutation.error, "任务还没有取消，请重试。")
        : undefined;

  return (
    <div className="flex min-h-[calc(100dvh-var(--sh-topbar-height))] flex-col bg-[var(--sh-surface-canvas)]">
      <header className="flex min-h-14 items-center gap-3 border-b border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-4 md:px-6">
        <Link
          aria-label="返回创作中心"
          className="grid size-9 place-items-center rounded-[var(--sh-radius-sm)] text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)]"
          to="/app/creation"
        >
          <ChevronLeft aria-hidden="true" className="size-5" />
        </Link>
        <div className="min-w-0">
          <h1 className="truncate font-semibold text-[var(--sh-ink-strong)]">{config.title}</h1>
          <p className="truncate text-xs text-[var(--sh-ink-muted)]">独立创作</p>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-[1120px] flex-1 flex-col gap-4 px-4 py-4 md:px-6">
        <CreationSessionBoundaryNotice />
        {!jobId ? <CreationSetupPanel settings={settings} type={type} /> : null}
        {jobId ? (
          <GenerationJobPanel
            cancelLabel={cancelMutation.isError ? "重试取消" : "取消任务"}
            cancelPending={cancelMutation.isPending || !writeReady}
            errorMessage={errorMessage}
            job={job}
            loading={jobQuery.isFetching}
            onCancel={writeReady && live ? () => cancelMutation.mutate() : undefined}
            onRefresh={() => void jobQuery.refetch()}
            title="创作任务"
          />
        ) : errorMessage ? (
          <p
            className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] p-4 text-sm text-[var(--sh-danger)]"
            role="alert"
          >
            {errorMessage}
          </p>
        ) : null}
        {job?.status === "succeeded" ? <CreationResultUnavailableNotice /> : null}
      </main>

      <CreationComposer
        advancedOpen={advancedOpen}
        advancedPanel={
          <CreationAdvancedPanel
            embedded
            onChange={(patch) => setAdvancedSettings((value) => ({ ...value, ...patch }))}
            referenceControlsAvailable={false}
            settings={advancedSettings}
          />
        }
        config={config}
        description={description}
        descriptionLabel={`描述你想创作的${type === "image" ? "图片" : type === "video" ? "视频" : "PPT"}`}
        disabled={!writeReady}
        onAdvancedOpenChange={setAdvancedOpen}
        onDescriptionChange={setDescription}
        onGenerate={() => createMutation.mutate()}
        onPromptReview={() => setPromptOpen(true)}
        onSettingsChange={(patch) => setSettings((value) => ({ ...value, ...patch }))}
        referenceUploadAvailable={false}
        settings={settings}
        stage={stage}
        type={type}
      />
      <PromptReviewDialog
        description={description}
        onOpenChange={setPromptOpen}
        onSave={setDescription}
        open={promptOpen}
      />
      {!writeReady ? (
        <p
          className="border-t border-[var(--sh-line-subtle)] bg-[var(--sh-warning-soft)] px-4 py-3 text-center text-sm text-[var(--sh-warning)]"
          role="status"
        >
          当前会话仅支持浏览创作台，登录与安全校验完成后才能发起创作。
        </p>
      ) : null}
    </div>
  );
}
