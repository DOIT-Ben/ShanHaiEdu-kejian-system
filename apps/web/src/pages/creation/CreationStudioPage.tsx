import { ChevronLeft } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CreationAdvancedPanel } from "@/features/creation-studio/CreationAdvancedPanel";
import type { CreationAdvancedSettings } from "@/features/creation-studio/CreationAdvancedPanel";
import { CreationComposer } from "@/features/creation-studio/CreationComposer";
import {
  cancelCreationTask,
  completeCreationTask,
  enqueueCreationTask,
  retryCreationTask,
  type CreationQueueStatus,
} from "@/features/creation-studio/creationQueue";
import { ImageEditDialog } from "@/features/creation-studio/ImageEditDialog";
import { ProjectAssetDrawer } from "@/features/creation-studio/ProjectAssetDrawer";
import {
  CreationResultsPanel,
  type CreationHistoryTurn,
} from "@/features/creation-studio/CreationResultsPanel";
import { CreationSetupPanel } from "@/features/creation-studio/CreationSetupPanel";
import { downloadCreationResult } from "@/features/creation-studio/downloadCreationResult";
import {
  buildCreationResultId,
  clampCreationCandidate,
  type CreationSettings,
  type CreationStage,
  type StudioType,
} from "@/features/creation-studio/model";
import { PromptReviewDialog } from "@/features/creation-studio/PromptReviewDialog";
import {
  createProjectVideoAssetPackage,
  createProjectVideoShotPackage,
} from "@/features/creation-studio/projectCreationPackage";
import { studioRegistry } from "@/features/creation-studio/registry";
import {
  SaveToProjectDialog,
  type SaveResultDescriptor,
} from "@/features/save-to-project/SaveToProjectDialog";
import { useMockRuntime } from "@/shared/api/mockClient";
import {
  commitCreationNode,
  readCreationDraft,
  readCreationQueue,
  readLatestCreationRuntime,
  saveCreationDraft,
  saveCreationQueue,
} from "@/features/creation-studio/creationRuntimeAdapter";
import { listMockSavedResults, saveMockResult } from "@/shared/api/mocks/savedResults";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import { markVideoAssetsDependentsStale } from "@/features/workbench/lib/invalidateDependents";
import { ProjectStepNavigation } from "@/features/workbench/components/ProjectStepNavigation";

const creationStages: CreationStage[] = [
  "adopted",
  "cancelled",
  "draft",
  "failed",
  "queued",
  "ready",
  "running",
  "saved",
];

type SavedCreation = {
  advancedSettings: CreationAdvancedSettings;
  candidate: number;
  description: string;
  generation: number;
  hasUnappliedChanges: boolean;
  history: CreationHistoryTurn[];
  projectId?: string;
  savedTarget?: string;
  settings: CreationSettings;
  stage: CreationStage;
};

function getCreationDescription(type: StudioType) {
  if (type === "video") {
    return "三瓶果汁依次落在桌面，镜头向前推进并停在不同标签上。人物发现只看数字无法公平比较。";
  }
  if (type === "presentation") {
    return "为六年级学生制作一套认识百分数的课堂 PPT，强调整体与部分的关系，每页一个教学任务。";
  }
  return "三瓶不同标签的果汁放在自然光木桌上，纸艺微缩风格，标签不出现准确文字和数字。";
}

export function CreationStudioPage({ type }: { type: StudioType }) {
  const config = studioRegistry[type];
  const runtime = useMockRuntime();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedProjectId = searchParams.get("projectId") ?? undefined;
  const requestedLessonId = searchParams.get("lessonId") ?? undefined;
  const requestedPackage = searchParams.get("package");
  const packageMode =
    (type === "image" && requestedPackage === "video-assets") ||
    (type === "video" && requestedPackage === "video-shots");
  const packageItems = useMemo(() => {
    if (!packageMode || !requestedProjectId || !requestedLessonId) return [];
    return type === "video"
      ? createProjectVideoShotPackage(runtime, requestedProjectId, requestedLessonId)
      : createProjectVideoAssetPackage(runtime, requestedProjectId, requestedLessonId);
  }, [packageMode, requestedLessonId, requestedProjectId, runtime, type]);
  const packageKind = requestedPackage ?? "standalone";
  const packageStatePrefix =
    requestedProjectId && requestedLessonId
      ? `creation:${type}:project:${requestedProjectId}:lesson:${requestedLessonId}:package:${packageKind}`
      : undefined;
  const workspaceKey = packageStatePrefix ? `${packageStatePrefix}:workspace` : undefined;
  const workspaceState = readCreationDraft<{ activeItemId?: string }>(runtime, workspaceKey ?? "");
  const requestedItemId =
    workspaceState?.activeItemId ??
    searchParams.get("itemId") ??
    searchParams.get("assetId") ??
    searchParams.get("shotId") ??
    packageItems[0]?.id;
  const packageItem = packageItems.find((item) => item.id === requestedItemId);
  const packageItemStateKey = (itemId: string) =>
    packageStatePrefix ? `${packageStatePrefix}:item:${itemId}` : `creation:${type}:state`;
  const stateKey =
    packageItem && packageStatePrefix
      ? packageItemStateKey(packageItem.id)
      : `creation:${type}:state`;
  const queueKey = packageStatePrefix ? `${packageStatePrefix}:queue` : `creation:${type}:queue`;
  const queueItemId = packageItem?.id ?? "standalone";
  const packageQueue = readCreationQueue(runtime, queueKey);
  const stored = readCreationDraft<Partial<SavedCreation>>(runtime, stateKey);
  const fallbackDescription = packageItem?.prompt ?? getCreationDescription(type);
  const stage = creationStages.includes(stored?.stage as CreationStage)
    ? (stored?.stage as CreationStage)
    : "draft";
  const candidateCount = stored?.settings?.candidateCount ?? "3";
  const candidate = clampCreationCandidate(
    typeof stored?.candidate === "number" ? stored.candidate : 0,
    candidateCount,
  );
  const generation = typeof stored?.generation === "number" ? stored.generation : 0;
  const hasUnappliedChanges = stored?.hasUnappliedChanges === true;
  const history = useMemo(
    () => (Array.isArray(stored?.history) ? stored.history : []),
    [stored?.history],
  );
  const description =
    typeof stored?.description === "string" ? stored.description : fallbackDescription;
  const savedTarget = typeof stored?.savedTarget === "string" ? stored.savedTarget : undefined;
  const projectId = requestedProjectId ?? stored?.projectId;
  const project = runtime.projects.find((item) => item.id === projectId);
  const lesson =
    projectId && requestedLessonId
      ? getApprovedProjectLessons(runtime, projectId).find((item) => item.id === requestedLessonId)
      : undefined;
  const settings = useMemo<CreationSettings>(
    () => ({
      candidateCount,
      duration: stored?.settings?.duration ?? packageItem?.duration ?? "10",
      model: stored?.settings?.model ?? "balanced",
      ratio: stored?.settings?.ratio ?? packageItem?.ratio ?? (type === "image" ? "auto" : "16:9"),
      referenceName:
        stored?.settings?.referenceName ?? packageItem?.referenceNames?.join("、") ?? "",
      style: stored?.settings?.style ?? packageItem?.style ?? "paper",
    }),
    [candidateCount, packageItem, stored?.settings, type],
  );
  const advancedSettings = useMemo<CreationAdvancedSettings>(
    () => ({
      composition:
        stored?.advancedSettings?.composition ??
        "主体位于画面中部，保留清晰前后层次；不出现复杂背景。",
      negativePrompt:
        stored?.advancedSettings?.negativePrompt ??
        "文字、水印、Logo、准确数字、过度卡通化、恐怖元素。",
      referenceStrength: stored?.advancedSettings?.referenceStrength ?? 65,
    }),
    [stored?.advancedSettings],
  );
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [promptOpen, setPromptOpen] = useState(false);
  const [imageEditOpen, setImageEditOpen] = useState(false);
  const [assetDrawerOpen, setAssetDrawerOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const saveTriggerRef = useRef<HTMLButtonElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const descriptionLabel =
    type === "video" ? "画面怎样变化" : type === "presentation" ? "课件主题与课堂用途" : "画面内容";
  const savedSlotKeys = useMemo(
    () =>
      new Set(
        projectId ? listMockSavedResults(runtime, projectId).map((item) => item.slotKey) : [],
      ),
    [projectId, runtime],
  );

  const updateCreation = (patch: Partial<SavedCreation>) => {
    saveCreationDraft(stateKey, {
      advancedSettings,
      candidate,
      description,
      generation,
      hasUnappliedChanges,
      history,
      ...(projectId ? { projectId } : {}),
      settings,
      stage,
      ...patch,
    });
  };

  const changedOutputPatch =
    stage === "draft" || stage === "cancelled" || stage === "failed"
      ? {}
      : {
          hasUnappliedChanges: true,
          savedTarget: undefined,
          stage: stage === "running" ? ("running" as const) : ("ready" as const),
        };

  useEffect(() => {
    if (packageMode || stage !== "running") return;
    const timer = window.setTimeout(() => {
      const latestRuntime = readLatestCreationRuntime();
      const latestQueue = readCreationQueue(latestRuntime, queueKey);
      saveCreationDraft(stateKey, {
        advancedSettings,
        candidate: 0,
        description,
        generation,
        hasUnappliedChanges: false,
        history,
        ...(projectId ? { projectId } : {}),
        settings,
        stage: "ready",
      });
      saveCreationQueue(queueKey, completeCreationTask(latestQueue, queueItemId), {
        ...(projectId ? { projectId } : {}),
      });
    }, 1450);
    return () => window.clearTimeout(timer);
  }, [
    advancedSettings,
    candidate,
    description,
    generation,
    history,
    packageMode,
    projectId,
    settings,
    stage,
    stateKey,
    queueItemId,
    queueKey,
  ]);

  const runningPackageItemId = Object.keys(packageQueue).find(
    (itemId) => packageQueue[itemId]?.status === "running",
  );

  useEffect(() => {
    if (!packageStatePrefix || !runningPackageItemId) return;
    const timer = window.setTimeout(() => {
      const latestRuntime = readLatestCreationRuntime();
      const runningStateKey = `${packageStatePrefix}:item:${runningPackageItemId}`;
      const runningStored = latestRuntime.drafts[runningStateKey]?.value as
        Partial<SavedCreation> | undefined;
      const latestQueue = readCreationQueue(latestRuntime, queueKey);
      const nextQueue = completeCreationTask(latestQueue, runningPackageItemId);
      saveCreationDraft(runningStateKey, {
        ...runningStored,
        candidate: 0,
        hasUnappliedChanges: false,
        stage: "ready",
      });
      const nextRunningId = Object.keys(nextQueue).find(
        (itemId) => nextQueue[itemId]?.status === "running",
      );
      if (nextRunningId) {
        const nextStateKey = `${packageStatePrefix}:item:${nextRunningId}`;
        const nextStored = latestRuntime.drafts[nextStateKey]?.value as
          Partial<SavedCreation> | undefined;
        saveCreationDraft(nextStateKey, { ...nextStored, stage: "running" });
      }
      saveCreationQueue(queueKey, nextQueue, {
        ...(requestedLessonId ? { lessonId: requestedLessonId } : {}),
        ...(projectId ? { projectId } : {}),
      });
    }, 1450);
    return () => window.clearTimeout(timer);
  }, [packageStatePrefix, projectId, queueKey, requestedLessonId, runningPackageItemId]);

  const generate = (nextDescription = description) => {
    const normalizedDescription = nextDescription.trim();
    if (!normalizedDescription) return;
    setAdvancedOpen(false);
    setPromptOpen(false);
    const nextQueue = enqueueCreationTask(packageQueue, queueItemId);
    const nextPackageStage = nextQueue[queueItemId]?.status === "running" ? "running" : "queued";
    const nextHistory =
      generation > 0 && ["ready", "adopted", "saved"].includes(stage)
        ? [...history, { candidate, generation, prompt: description, ratio: settings.ratio }]
        : history;
    updateCreation({
      description: normalizedDescription,
      generation: generation + 1,
      hasUnappliedChanges: false,
      history: nextHistory,
      savedTarget: undefined,
      stage: nextPackageStage,
    });
    saveCreationQueue(queueKey, nextQueue, {
      ...(requestedLessonId ? { lessonId: requestedLessonId } : {}),
      ...(projectId ? { projectId } : {}),
    });
    window.requestAnimationFrame(() => {
      const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth";
      const content = mainRef.current;
      content?.scrollTo({ behavior, top: content.scrollHeight });
    });
  };

  const importPackageItem = (itemId: string) => {
    if (!packageStatePrefix) return;
    const item = packageItems.find((candidateItem) => candidateItem.id === itemId);
    if (!item) return;
    const targetKey = `${packageStatePrefix}:item:${item.id}`;
    const existing = readCreationDraft<Partial<SavedCreation>>(runtime, targetKey);
    saveCreationDraft(targetKey, {
      ...existing,
      advancedSettings: existing?.advancedSettings ?? advancedSettings,
      candidate: existing?.candidate ?? 0,
      description: item.prompt,
      generation: existing?.generation ?? 0,
      hasUnappliedChanges: false,
      history: existing?.history ?? [],
      ...(projectId ? { projectId } : {}),
      settings: {
        ...settings,
        duration: item.duration ?? settings.duration,
        ratio: item.ratio,
        referenceName: item.referenceNames?.join("、") ?? "",
        style: item.style,
      },
      stage: existing?.stage ?? "draft",
    });
    if (workspaceKey) {
      saveCreationDraft(
        workspaceKey,
        { activeItemId: item.id },
        {
          ...(requestedLessonId ? { lessonId: requestedLessonId } : {}),
          ...(projectId ? { projectId } : {}),
        },
      );
    }
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("itemId", item.id);
    nextSearchParams.delete("assetId");
    nextSearchParams.delete("shotId");
    void navigate({ search: nextSearchParams.toString() }, { replace: true });
  };

  const generateAllPackageItems = () => {
    if (!packageStatePrefix || packageItems.length === 0) return;
    let nextQueue = packageQueue;
    for (const item of packageItems) {
      nextQueue = enqueueCreationTask(nextQueue, item.id);
      const itemKey = `${packageStatePrefix}:item:${item.id}`;
      const existing = readCreationDraft<Partial<SavedCreation>>(runtime, itemKey);
      saveCreationDraft(itemKey, {
        ...existing,
        advancedSettings: existing?.advancedSettings ?? advancedSettings,
        candidate: existing?.candidate ?? 0,
        description: existing?.description ?? item.prompt,
        generation: existing?.generation ?? 1,
        hasUnappliedChanges: false,
        history: existing?.history ?? [],
        ...(projectId ? { projectId } : {}),
        settings: {
          ...settings,
          duration: item.duration ?? settings.duration,
          ratio: item.ratio,
          referenceName: item.referenceNames?.join("、") ?? "",
          style: item.style,
        },
        stage: nextQueue[item.id]?.status === "running" ? "running" : "queued",
      });
    }
    saveCreationQueue(queueKey, nextQueue, {
      ...(requestedLessonId ? { lessonId: requestedLessonId } : {}),
      ...(projectId ? { projectId } : {}),
    });
  };

  const cancelPackageTask = (itemId: string) => {
    if (!packageStatePrefix) return;
    const nextQueue = cancelCreationTask(packageQueue, itemId);
    const itemKey = `${packageStatePrefix}:item:${itemId}`;
    const itemStored = readCreationDraft<Partial<SavedCreation>>(runtime, itemKey);
    saveCreationDraft(itemKey, { ...itemStored, stage: "cancelled" });
    const nextRunningId = Object.keys(nextQueue).find(
      (candidateId) => nextQueue[candidateId]?.status === "running",
    );
    if (nextRunningId) {
      const nextKey = `${packageStatePrefix}:item:${nextRunningId}`;
      const nextStored = readCreationDraft<Partial<SavedCreation>>(runtime, nextKey);
      saveCreationDraft(nextKey, { ...nextStored, stage: "running" });
    }
    saveCreationQueue(queueKey, nextQueue, {
      ...(requestedLessonId ? { lessonId: requestedLessonId } : {}),
      ...(projectId ? { projectId } : {}),
    });
  };

  const retryPackageTask = (itemId: string) => {
    if (!packageStatePrefix) return;
    const nextQueue = retryCreationTask(packageQueue, itemId);
    const itemKey = `${packageStatePrefix}:item:${itemId}`;
    const itemStored = readCreationDraft<Partial<SavedCreation>>(runtime, itemKey);
    saveCreationDraft(itemKey, {
      ...itemStored,
      generation: (itemStored?.generation ?? 0) + 1,
      stage: nextQueue[itemId]?.status === "running" ? "running" : "queued",
    });
    saveCreationQueue(queueKey, nextQueue, {
      ...(requestedLessonId ? { lessonId: requestedLessonId } : {}),
      ...(projectId ? { projectId } : {}),
    });
  };

  const result: SaveResultDescriptor = {
    id: `${buildCreationResultId(type, generation, candidate)}${packageItem ? `-${packageItem.id}` : ""}`,
    preview: { candidate, generation, ratio: settings.ratio },
    title: packageItem
      ? `${packageItem.title} · 作品 ${String(candidate + 1)}`
      : `${config.title} · 作品 ${String(candidate + 1)}`,
    type: type === "presentation" ? "ppt_page" : type,
  };
  const sharedSlot =
    type === "image"
      ? { key: "project.shared-images", label: "项目通用教学图片" }
      : type === "video"
        ? { key: "project.shared-videos", label: "项目通用视频素材" }
        : { key: "project.shared-presentations", label: "项目通用课件" };
  const saveToKnownProject = (targetProjectId: string) => {
    const savedResult = saveMockResult({
      lessonLabel: lesson?.title ?? "独立创作",
      projectId: targetProjectId,
      ...(result.preview ? { preview: result.preview } : {}),
      replaceMode: packageItem ? "replace" : "append",
      resultId: result.id,
      slotKey: packageItem?.slotKey ?? `${sharedSlot.key}:${result.id}`,
      slotLabel: packageItem?.slotLabel ?? sharedSlot.label,
      title: result.title,
      type: result.type,
    });
    const projectTitle = runtime.projects.find((item) => item.id === savedResult.projectId)?.title;
    updateCreation({
      projectId: savedResult.projectId,
      savedTarget: `${projectTitle ?? "目标项目"} · ${savedResult.slotLabel}`,
      stage: "saved",
    });
    if (packageItem && requestedLessonId) {
      const latestRuntime = readLatestCreationRuntime();
      const packageResultIds = Object.fromEntries(
        listMockSavedResults(latestRuntime, targetProjectId)
          .filter((item) =>
            packageItems.some((packageAsset) => packageAsset.slotKey === item.slotKey),
          )
          .map((item) => [
            packageItems.find((packageAsset) => packageAsset.slotKey === item.slotKey)?.id ??
              item.slotKey,
            item.resultId,
          ]),
      );
      const allPackageItemsSaved = packageItems.every((item) => item.id in packageResultIds);
      if (packageKind === "video-assets") {
        const approvedKey = `project:${targetProjectId}:lesson:${requestedLessonId}:video-assets:approved`;
        const previous = latestRuntime.drafts[approvedKey]?.value as
          { resultIds?: Record<string, string> } | undefined;
        if (allPackageItemsSaved) {
          if (JSON.stringify(previous?.resultIds ?? {}) !== JSON.stringify(packageResultIds)) {
            markVideoAssetsDependentsStale(latestRuntime, targetProjectId, requestedLessonId);
          }
          saveCreationDraft(
            approvedKey,
            { resultIds: packageResultIds },
            { lessonId: requestedLessonId, nodeKey: "video-assets", projectId: targetProjectId },
          );
        }
        commitCreationNode(targetProjectId, requestedLessonId, "video-assets", {
          stale_reason: null,
          status: allPackageItemsSaved ? "approved" : "review_required",
          title: "制作镜头图片",
        });
      } else if (packageKind === "video-shots") {
        saveCreationDraft(
          `project:${targetProjectId}:lesson:${requestedLessonId}:final-video:shots`,
          { resultIds: packageResultIds },
          { lessonId: requestedLessonId, nodeKey: "final-video", projectId: targetProjectId },
        );
        commitCreationNode(targetProjectId, requestedLessonId, "final-video", {
          stale_reason: null,
          status: allPackageItemsSaved ? "review_required" : "partially_completed",
          title: "生成课堂导入视频",
        });
      }
    }
  };
  const advance = () => {
    if (stage === "ready") {
      if (packageItem && projectId) saveToKnownProject(projectId);
      else updateCreation({ stage: "adopted" });
    } else if (stage === "adopted") {
      if (projectId) saveToKnownProject(projectId);
      else setSaveOpen(true);
    }
  };

  const changeCandidate = (nextCandidate: number) => {
    updateCreation({
      candidate: nextCandidate,
      savedTarget: undefined,
      stage: stage === "adopted" || stage === "saved" ? "ready" : stage,
    });
  };
  const sourceStep = type === "video" ? "fine-storyboard" : "video-assets";
  const workbenchBase =
    projectId && requestedLessonId
      ? `/app/projects/${projectId}/lessons/${requestedLessonId}/work`
      : undefined;
  const taskStatuses: Record<string, CreationQueueStatus> = Object.fromEntries(
    packageItems.map((item) => [item.id, packageQueue[item.id]?.status ?? "idle"]),
  );

  return (
    <div
      className="sh-creation-studio flex h-[calc(100dvh-var(--sh-topbar-height))] flex-col overflow-hidden bg-[var(--sh-surface-canvas)]"
      data-testid="creation-studio"
    >
      <header className="flex min-h-11 shrink-0 items-center gap-2 border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)]/88 px-4 backdrop-blur-sm md:px-6">
        <Link
          aria-label={packageItem ? "返回项目工作台" : "返回创作中心"}
          className="grid size-9 place-items-center rounded-[var(--sh-radius-sm)] text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)]"
          to={
            packageItem && projectId && requestedLessonId
              ? `/app/projects/${projectId}/lessons/${requestedLessonId}/work/${sourceStep}`
              : "/app/creation"
          }
        >
          <ChevronLeft aria-hidden="true" className="size-5" />
        </Link>
        <h1 className="truncate font-semibold text-[var(--sh-ink-strong)]">{config.title}</h1>
        {project ? (
          <span className="ml-auto max-w-[min(48vw,360px)] truncate text-sm font-medium text-[var(--sh-ink-muted)]">
            {project.title}
            {lesson ? ` · ${lesson.title}` : ""}
          </span>
        ) : null}
      </header>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {packageItem && workbenchBase && projectId && requestedLessonId ? (
          <aside
            className="hidden h-full w-[var(--sh-project-sidebar-width)] shrink-0 overflow-y-auto border-r border-[var(--sh-line-default)] bg-[var(--sh-brand-50)] md:block"
            data-step-scroll-container
          >
            <div className="flex h-12 items-center px-5 text-xs font-semibold text-[var(--sh-ink-muted)]">
              课时制作流程
            </div>
            <ProjectStepNavigation
              activeStepKey={sourceStep}
              base={workbenchBase}
              lessonId={requestedLessonId}
              projectId={projectId}
            />
          </aside>
        ) : null}

        <div className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
          <section
            aria-label="创作工作区"
            className={`flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-2.5 transition-[padding] duration-[var(--sh-duration-normal)] md:px-6 ${assetDrawerOpen ? "lg:pr-[420px]" : "lg:pr-20"}`}
            ref={mainRef}
            tabIndex={-1}
          >
            <div className="min-h-0 flex-1">
              {stage === "draft" || stage === "cancelled" || stage === "failed" ? (
                <CreationSetupPanel settings={settings} type={type} />
              ) : (
                <CreationResultsPanel
                  candidate={candidate}
                  candidateCount={Math.max(1, Number.parseInt(settings.candidateCount, 10) || 3)}
                  generation={generation}
                  hasUnappliedChanges={hasUnappliedChanges}
                  history={history}
                  onAdvance={advance}
                  onCandidateChange={changeCandidate}
                  onDownload={() => {
                    void downloadCreationResult({
                      candidate,
                      ratio: settings.ratio,
                      title: config.title,
                      type,
                    });
                  }}
                  onViewProjectAssets={
                    projectId
                      ? () => {
                          void navigate(`/app/projects/${projectId}/results`);
                        }
                      : undefined
                  }
                  prompt={description}
                  ratio={settings.ratio}
                  saveTriggerRef={saveTriggerRef}
                  savedTarget={savedTarget}
                  stage={stage}
                  type={type}
                />
              )}
            </div>
          </section>

          <div
            className={`transition-[padding] duration-[var(--sh-duration-normal)] ${assetDrawerOpen ? "lg:pr-[396px]" : ""}`}
          >
            <CreationComposer
              advancedOpen={advancedOpen}
              advancedPanel={
                <CreationAdvancedPanel
                  embedded
                  onChange={(patch) =>
                    updateCreation({
                      advancedSettings: { ...advancedSettings, ...patch },
                      ...changedOutputPatch,
                    })
                  }
                  settings={advancedSettings}
                />
              }
              config={config}
              description={description}
              descriptionLabel={descriptionLabel}
              onAdvancedOpenChange={setAdvancedOpen}
              onDescriptionChange={(nextDescription) =>
                updateCreation({ description: nextDescription, ...changedOutputPatch })
              }
              onGenerate={() => generate()}
              onImageEdit={type === "image" ? () => setImageEditOpen(true) : undefined}
              onPromptReview={() => setPromptOpen(true)}
              onSettingsChange={(patch) => {
                const nextSettings = { ...settings, ...patch };
                updateCreation({
                  candidate: clampCreationCandidate(candidate, nextSettings.candidateCount),
                  settings: nextSettings,
                  ...changedOutputPatch,
                });
              }}
              settings={settings}
              stage={stage}
              type={type}
            />
          </div>

          {packageItem && project && lesson ? (
            <ProjectAssetDrawer
              activeId={packageItem.id}
              items={packageItems}
              lessonTitle={lesson.title}
              onCancel={cancelPackageTask}
              onGenerateAll={generateAllPackageItems}
              onImport={importPackageItem}
              onOpenChange={setAssetDrawerOpen}
              onRetry={retryPackageTask}
              projectTitle={project.title}
              savedSlotKeys={savedSlotKeys}
              taskStatuses={taskStatuses}
            />
          ) : null}
        </div>
      </div>

      <PromptReviewDialog
        description={description}
        onOpenChange={setPromptOpen}
        onRegenerate={stage === "draft" ? undefined : generate}
        onSave={(nextDescription) =>
          updateCreation({ description: nextDescription, ...changedOutputPatch })
        }
        open={promptOpen}
      />
      {type === "image" ? (
        <ImageEditDialog
          description={description}
          onApply={generate}
          onOpenChange={setImageEditOpen}
          open={imageEditOpen}
        />
      ) : null}
      <SaveToProjectDialog
        onOpenChange={setSaveOpen}
        onSaved={(savedResult) => {
          const projectTitle = runtime.projects.find(
            (project) => project.id === savedResult.projectId,
          )?.title;
          updateCreation({
            projectId: savedResult.projectId,
            savedTarget: `${projectTitle ?? "目标项目"} · ${savedResult.slotLabel}`,
            stage: "saved",
          });
        }}
        open={saveOpen}
        result={result}
        returnFocusRef={saveTriggerRef}
      />
    </div>
  );
}
