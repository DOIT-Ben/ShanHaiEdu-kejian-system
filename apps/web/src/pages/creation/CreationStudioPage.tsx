import { Check, ChevronLeft } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CreationAdvancedPanel } from "@/features/creation-studio/CreationAdvancedPanel";
import type { CreationAdvancedSettings } from "@/features/creation-studio/CreationAdvancedPanel";
import { CreationComposer } from "@/features/creation-studio/CreationComposer";
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

const creationStages: CreationStage[] = ["draft", "running", "ready", "adopted", "saved"];

type SavedCreation = {
  advancedSettings: CreationAdvancedSettings;
  candidate: number;
  description: string;
  generation: number;
  hasUnappliedChanges: boolean;
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
  const settings = useMemo<CreationSettings>(
    () => ({
      candidateCount,
      duration: stored?.settings?.duration ?? "10",
      model: stored?.settings?.model ?? "balanced",
      ratio: stored?.settings?.ratio ?? (type === "image" ? "1:1" : "16:9"),
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
        settings,
        stage: "ready",
      });
    }, 1450);
    return () => window.clearTimeout(timer);
  }, [advancedSettings, candidate, description, generation, settings, stage, stateKey]);

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

  const advance = () => {
    if (stage === "ready") {
      updateCreation({ stage: "adopted" });
    } else if (stage === "adopted") {
      setSaveOpen(true);
    }
  };

  const changeCandidate = (nextCandidate: number) => {
    updateCreation({
      candidate: nextCandidate,
      savedTarget: undefined,
      stage: stage === "adopted" || stage === "saved" ? "ready" : stage,
    });
  };

  const result: SaveResultDescriptor = {
    id: buildCreationResultId(type, generation, candidate),
    preview: { candidate, generation, ratio: settings.ratio },
    title: `${config.title} · 作品 ${String(candidate + 1)}`,
    type: type === "presentation" ? "ppt_page" : type,
  };
  const saveStatus = {
    adopted: "已选中，保存后进入项目",
    draft: "本地草稿已保存",
    ready: type === "video" ? "关键帧已准备" : "作品已完成",
    running: "正在创作",
    saved: type === "video" ? "关键帧已保存到项目" : "已保存到项目",
  }[stage];

  return (
    <div
      className="sh-creation-studio flex h-[calc(100dvh-var(--sh-topbar-height))] flex-col overflow-hidden bg-[var(--sh-surface-canvas)]"
      data-testid="creation-studio"
    >
      <header className="flex min-h-12 shrink-0 flex-wrap items-center gap-3 border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)]/88 px-4 shadow-[var(--sh-shadow-card)] backdrop-blur-sm md:px-6">
        <Link
          aria-label="返回创作中心"
          className="grid size-10 place-items-center rounded-[var(--sh-radius-sm)] text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)]"
          to="/app/creation"
        >
          <ChevronLeft aria-hidden="true" className="size-5" />
        </Link>
        <div className="min-w-0">
          <p className="text-xs text-[var(--sh-ink-muted)]">我的创作桌 · 独立作品</p>
          <h1 className="truncate font-semibold text-[var(--sh-ink-strong)]">{config.title}</h1>
        </div>
        <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-[var(--sh-success-soft)] px-2.5 py-1 text-xs font-medium text-[var(--sh-success-strong)]">
          <Check aria-hidden="true" className="size-3.5" />
          {saveStatus}
        </span>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto px-4 py-3 md:px-6" ref={mainRef}>
        {stage === "draft" ? (
          <CreationSetupPanel config={config} settings={settings} type={type} />
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
            ratio={settings.ratio}
            saveTriggerRef={saveTriggerRef}
            savedTarget={savedTarget}
            stage={stage}
            type={type}
          />
        )}
      </main>

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
        hasUnappliedChanges={hasUnappliedChanges}
        onAdvancedOpenChange={setAdvancedOpen}
        onDescriptionChange={(nextDescription) =>
          updateCreation({ description: nextDescription, ...changedOutputPatch })
        }
        onGenerate={() => generate()}
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
      <SaveToProjectDialog
        onOpenChange={setSaveOpen}
        onSaved={(savedResult) => {
          const projectTitle = runtime.projects.find(
            (project) => project.id === savedResult.projectId,
          )?.title;
          updateCreation({
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
