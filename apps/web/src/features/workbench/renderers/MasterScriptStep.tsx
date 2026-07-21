import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Check,
  PencilLine,
  Plus,
  RefreshCw,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { createTopicIntroOptions, introOptions } from "@/features/intro-options/data";
import { readIntroOptionsDraft, resolveIntroOption } from "@/features/intro-options/state";
import {
  MarkdownDocument,
  type DocumentMode,
} from "@/features/workbench/components/MarkdownDocument";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import {
  parseMasterScript,
  serializeMasterScript,
  type ScriptScene,
} from "@/features/workbench/lib/documentMarkdown";
import {
  createMasterScriptFromIntro,
  masterScriptNeedsRefresh,
} from "@/features/workbench/lib/masterScriptFromIntro";
import { markMasterScriptDependentsStale } from "@/features/workbench/lib/invalidateDependents";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import { saveMockDraft, updateMockNodeState, useMockRuntime } from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { demoProjectId } from "@/shared/data/mockData";

export function MasterScriptStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const availableIntroOptions =
    projectId === demoProjectId || !project
      ? introOptions
      : createTopicIntroOptions(project.knowledge_point);
  const defaultOption = availableIntroOptions[0];
  if (!defaultOption) throw new Error("缺少课堂导入方案");
  const introDraft = readIntroOptionsDraft(
    runtime.drafts[`project:${projectId}:lesson:${lessonId}:intro-options`]?.value,
    defaultOption.key,
  );
  const adoptedOptionBase =
    availableIntroOptions.find((option) => option.key === introDraft.adoptedKey) ?? defaultOption;
  const adoptedOption = resolveIntroOption(
    adoptedOptionBase,
    introDraft,
    introDraft.adoptedRevision,
  );
  const generated = createMasterScriptFromIntro(adoptedOption);
  const draftKey = `project:${projectId}:lesson:${lessonId}:master-script`;
  const approvedKey = `${draftKey}:approved`;
  const nodeStatus = runtime.nodeStates[`${projectId}:${lessonId}:master-script`]?.status;
  type SavedMasterScript =
    | {
        markdown?: string;
        scenes?: ScriptScene[];
        sourceIntroKey?: string;
        sourceIntroRevision?: number;
        summary?: string;
        title?: string;
      }
    | undefined;
  const currentSaved = runtime.drafts[draftKey]?.value as SavedMasterScript;
  const approvedSaved = runtime.drafts[approvedKey]?.value as SavedMasterScript;
  const saved = nodeStatus === "approved" ? approvedSaved : (currentSaved ?? approvedSaved);
  const initialItems = saved?.scenes ?? generated.scenes;
  const initialTitle = saved?.title ?? generated.title;
  const initialSummary = saved?.summary ?? generated.summary;
  const [items, setItems] = useState(initialItems);
  const [title, setTitle] = useState(initialTitle);
  const [summary, setSummary] = useState(initialSummary);
  const [markdown, setMarkdown] = useState(
    saved?.markdown ??
      serializeMasterScript(initialTitle, initialSummary, initialItems, adoptedOption.handoff),
  );
  const [mode, setMode] = useState<DocumentMode>("preview");
  const [dirty, setDirty] = useState(false);
  const stale =
    nodeStatus === "stale" ||
    masterScriptNeedsRefresh(saved, {
      key: introDraft.adoptedKey ?? adoptedOption.key,
      revision: introDraft.adoptedRevision ?? 0,
    });
  const approved = nodeStatus === "approved" && !stale;
  const { openContextDrawer } = useWorkbenchUi();

  const persistScript = () => {
    const parsed = parseMasterScript(markdown, { scenes: items, summary, title });
    setItems(parsed.scenes);
    setTitle(parsed.title);
    setSummary(parsed.summary);
    saveMockDraft(
      draftKey,
      {
        markdown,
        scenes: parsed.scenes,
        sourceIntroKey: introDraft.adoptedKey,
        sourceIntroRevision: introDraft.adoptedRevision,
        summary: parsed.summary,
        title: parsed.title,
      },
      { lessonId, nodeKey: "master-script", projectId },
    );
    setDirty(false);
  };

  const approveScript = () => {
    const parsed = parseMasterScript(markdown, { scenes: items, summary, title });
    const nextValue = {
      markdown,
      scenes: parsed.scenes,
      sourceIntroKey: introDraft.adoptedKey,
      sourceIntroRevision: introDraft.adoptedRevision,
      summary: parsed.summary,
      title: parsed.title,
    };
    const changed =
      typeof approvedSaved?.markdown === "string" && approvedSaved.markdown !== markdown;
    if (changed) markMasterScriptDependentsStale(runtime, projectId, lessonId);
    setItems(parsed.scenes);
    setTitle(parsed.title);
    setSummary(parsed.summary);
    saveMockDraft(draftKey, nextValue, { lessonId, nodeKey: "master-script", projectId });
    saveMockDraft(approvedKey, nextValue, { lessonId, nodeKey: "master-script", projectId });
    updateMockNodeState(projectId, lessonId, "master-script", {
      stale_reason: null,
      status: "approved",
      title: "编写母版剧本",
    });
    setDirty(false);
  };

  const refreshFromAdoptedOption = () => {
    const next = createMasterScriptFromIntro(adoptedOption);
    const nextMarkdown = serializeMasterScript(
      next.title,
      next.summary,
      next.scenes,
      adoptedOption.handoff,
    );
    setItems(next.scenes);
    setTitle(next.title);
    setSummary(next.summary);
    setMarkdown(nextMarkdown);
    setDirty(false);
    saveMockDraft(
      draftKey,
      {
        markdown: nextMarkdown,
        scenes: next.scenes,
        sourceIntroKey: introDraft.adoptedKey,
        sourceIntroRevision: introDraft.adoptedRevision,
        summary: next.summary,
        title: next.title,
      },
      { lessonId, nodeKey: "master-script", projectId },
    );
    updateMockNodeState(projectId, lessonId, "master-script", {
      stale_reason: null,
      status: "review_required",
      title: "编写母版剧本",
    });
  };

  const addScene = () => {
    const nextItems = [
      ...items,
      {
        action: "补充本场次中可被观察到的画面动作。",
        dialogue: "",
        duration: "待安排",
        narration: "补充与画面一致的旁白。",
        sound: "待补充声音意图。",
        title: "新增场次",
      },
    ];
    setItems(nextItems);
    setMarkdown(serializeMasterScript(title, summary, nextItems, adoptedOption.handoff));
    setDirty(true);
  };

  return (
    <WorkbenchPageFrame width="document">
      <FocusPageHeader
        action={
          stale ? (
            <Button onClick={refreshFromAdoptedOption} size="md">
              <RefreshCw aria-hidden="true" />
              根据新方案更新剧本
            </Button>
          ) : approved ? (
            <>
              <Button
                aria-label="重新编辑剧本"
                onClick={() => {
                  if (!runtime.drafts[approvedKey]) {
                    saveMockDraft(
                      approvedKey,
                      {
                        markdown,
                        scenes: items,
                        sourceIntroKey: introDraft.adoptedKey,
                        sourceIntroRevision: introDraft.adoptedRevision,
                        summary,
                        title,
                      },
                      { lessonId, nodeKey: "master-script", projectId },
                    );
                  }
                  updateMockNodeState(projectId, lessonId, "master-script", {
                    stale_reason: null,
                    status: "review_required",
                    title: "编写母版剧本",
                  });
                }}
                size="md"
                variant="secondary"
              >
                <PencilLine aria-hidden="true" />
                重新编辑剧本
              </Button>
              <Button asChild size="md">
                <Link to={`/app/projects/${projectId}/lessons/${lessonId}/work/rough-storyboard`}>
                  安排故事镜头
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </>
          ) : (
            <Button onClick={approveScript} size="md">
              <Check aria-hidden="true" />
              确认母版剧本
            </Button>
          )
        }
        eyebrow="当前要做：确认视频故事"
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : "review_required"} />
        }
        title={title}
      />
      {stale ? (
        <div className="mt-3 flex flex-wrap items-center gap-2 rounded-[var(--sh-radius-sm)] border border-[var(--sh-warning)]/30 bg-[var(--sh-warning-soft)] px-3 py-2 text-sm">
          <AlertTriangle aria-hidden="true" className="size-4 shrink-0 text-[var(--sh-warning)]" />
          <span className="min-w-0 flex-1 text-[var(--sh-ink-default)]">
            课堂导入已经改用“{adoptedOption.title}”。旧稿暂时保留为只读，更新后再确认。
          </span>
        </div>
      ) : null}
      <MarkdownDocument
        ariaLabel="母版剧本正文"
        dirty={dirty}
        extraActions={
          stale ? undefined : (
            <>
              <Button onClick={() => openContextDrawer("references")} size="sm" variant="quiet">
                <BookOpen aria-hidden="true" />
                导入方案
              </Button>
              {approved ? null : (
                <Button onClick={addScene} size="sm" variant="quiet">
                  <Plus aria-hidden="true" />
                  增加场次
                </Button>
              )}
            </>
          )
        }
        markdown={markdown}
        mode={mode}
        onChange={(nextMarkdown) => {
          const parsed = parseMasterScript(nextMarkdown, { scenes: items, summary, title });
          setMarkdown(nextMarkdown);
          setItems(parsed.scenes);
          setTitle(parsed.title);
          setSummary(parsed.summary);
          setDirty(true);
        }}
        onModeChange={setMode}
        onSave={persistScript}
        readOnly={approved || stale}
        title="完整故事稿"
      />
    </WorkbenchPageFrame>
  );
}
