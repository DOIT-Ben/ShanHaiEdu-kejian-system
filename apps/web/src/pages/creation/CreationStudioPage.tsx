import { ChevronLeft, FolderOpen } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CreationAdvancedPanel } from "@/features/creation-studio/CreationAdvancedPanel";
import type { CreationAdvancedSettings } from "@/features/creation-studio/CreationAdvancedPanel";
import { CreationComposer } from "@/features/creation-studio/CreationComposer";
import { ImageEditDialog } from "@/features/creation-studio/ImageEditDialog";
import { CreationResultsPanel } from "@/features/creation-studio/CreationResultsPanel";
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
import { studioRegistry } from "@/features/creation-studio/registry";
import {
  SaveToProjectDialog,
  type SaveResultDescriptor,
} from "@/features/save-to-project/SaveToProjectDialog";
import { saveMockDraft, useMockRuntime } from "@/shared/api/mocks/runtime";
import { saveMockResult } from "@/shared/api/mocks/savedResults";

const creationStages: CreationStage[] = ["draft", "running", "ready", "adopted", "saved"];

type SavedCreation = {
  advancedSettings: CreationAdvancedSettings;
  candidate: number;
  description: string;
  generation: number;
  hasUnappliedChanges: boolean;
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
  const stateKey = `creation:${type}:state`;
  const stored = runtime.drafts[stateKey]?.value as Partial<SavedCreation> | undefined;
  const fallbackDescription = getCreationDescription(type);
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
  const description =
    typeof stored?.description === "string" ? stored.description : fallbackDescription;
  const savedTarget = typeof stored?.savedTarget === "string" ? stored.savedTarget : undefined;
  const projectId = searchParams.get("projectId") ?? stored?.projectId;
  const project = runtime.projects.find((item) => item.id === projectId);
  const settings = useMemo<CreationSettings>(
    () => ({
      candidateCount,
      duration: stored?.settings?.duration ?? "10",
      model: stored?.settings?.model ?? "balanced",
      ratio: stored?.settings?.ratio ?? (type === "image" ? "auto" : "16:9"),
      referenceName: stored?.settings?.referenceName ?? "",
      style: stored?.settings?.style ?? "paper",
    }),
    [candidateCount, stored?.settings, type],
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
  const [saveOpen, setSaveOpen] = useState(false);
  const saveTriggerRef = useRef<HTMLButtonElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const descriptionLabel =
    type === "video" ? "画面怎样变化" : type === "presentation" ? "课件主题与课堂用途" : "画面内容";

  const updateCreation = (patch: Partial<SavedCreation>) => {
    saveMockDraft(stateKey, {
      advancedSettings,
      candidate,
      description,
      generation,
      hasUnappliedChanges,
      ...(projectId ? { projectId } : {}),
      settings,
      stage,
      ...patch,
    });
  };

  const changedOutputPatch =
    stage === "draft"
      ? {}
      : {
          hasUnappliedChanges: true,
          savedTarget: undefined,
          stage: stage === "running" ? ("running" as const) : ("ready" as const),
        };

  useEffect(() => {
    if (stage !== "running") return;
    const timer = window.setTimeout(() => {
      saveMockDraft(stateKey, {
        advancedSettings,
        candidate: 0,
        description,
        generation,
        hasUnappliedChanges: false,
        ...(projectId ? { projectId } : {}),
        settings,
        stage: "ready",
      });
    }, 1450);
    return () => window.clearTimeout(timer);
  }, [advancedSettings, candidate, description, generation, projectId, settings, stage, stateKey]);

  const generate = (nextDescription = description) => {
    const normalizedDescription = nextDescription.trim();
    if (!normalizedDescription) return;
    setAdvancedOpen(false);
    setPromptOpen(false);
    updateCreation({
      description: normalizedDescription,
      generation: generation + 1,
      hasUnappliedChanges: false,
      savedTarget: undefined,
      stage: "running",
    });
    window.requestAnimationFrame(() => {
      const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth";
      mainRef.current?.scrollTo({ behavior, top: 0 });
    });
  };

  const result: SaveResultDescriptor = {
    id: buildCreationResultId(type, generation, candidate),
    preview: { candidate, generation, ratio: settings.ratio },
    title: `${config.title} · 作品 ${String(candidate + 1)}`,
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
      lessonLabel: "独立创作",
      projectId: targetProjectId,
      ...(result.preview ? { preview: result.preview } : {}),
      replaceMode: "append",
      resultId: result.id,
      slotKey: `${sharedSlot.key}:${result.id}`,
      slotLabel: sharedSlot.label,
      title: result.title,
      type: result.type,
    });
    const projectTitle = runtime.projects.find((item) => item.id === savedResult.projectId)?.title;
    updateCreation({
      projectId: savedResult.projectId,
      savedTarget: `${projectTitle ?? "目标项目"} · ${savedResult.slotLabel}`,
      stage: "saved",
    });
  };
  const advance = () => {
    if (stage === "ready") {
      updateCreation({ stage: "adopted" });
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

  return (
    <div
      className="sh-creation-studio flex h-[calc(100dvh-var(--sh-topbar-height))] flex-col overflow-hidden bg-[var(--sh-surface-canvas)]"
      data-testid="creation-studio"
    >
      <header className="flex min-h-11 shrink-0 items-center gap-2 border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)]/88 px-4 backdrop-blur-sm md:px-6">
        <Link
          aria-label="返回创作中心"
          className="grid size-9 place-items-center rounded-[var(--sh-radius-sm)] text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)]"
          to="/app/creation"
        >
          <ChevronLeft aria-hidden="true" className="size-5" />
        </Link>
        <h1 className="truncate font-semibold text-[var(--sh-ink-strong)]">{config.title}</h1>
        {project ? (
          <Link
            aria-label={`查看${project.title}的项目资产`}
            className="ml-auto inline-flex min-w-0 items-center gap-1.5 rounded-[var(--sh-radius-sm)] px-2 py-1 text-sm font-medium text-[var(--sh-brand-700)] hover:bg-[var(--sh-brand-50)]"
            to={`/app/projects/${project.id}/results`}
          >
            <FolderOpen aria-hidden="true" className="size-4 shrink-0" />
            <span className="max-w-44 truncate">{project.title}</span>
            <span className="hidden sm:inline">· 项目资产</span>
          </Link>
        ) : null}
      </header>

      <section
        aria-label="创作工作区"
        className="min-h-0 flex-1 overflow-y-auto px-4 py-2.5 md:px-6"
        ref={mainRef}
      >
        {stage === "draft" ? (
          <CreationSetupPanel settings={settings} type={type} />
        ) : (
          <CreationResultsPanel
            candidate={candidate}
            candidateCount={Math.max(1, Number.parseInt(settings.candidateCount, 10) || 3)}
            generation={generation}
            hasUnappliedChanges={hasUnappliedChanges}
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
            ratio={settings.ratio}
            saveTriggerRef={saveTriggerRef}
            savedTarget={savedTarget}
            stage={stage}
            type={type}
          />
        )}
      </section>

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
