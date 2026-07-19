import { Check, PencilLine, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import {
  createTopicVideoStyles,
  demoVideoStyles,
  demoVideoTitle,
  type VideoStyle,
} from "@/features/workbench/lib/videoContent";
import { getApprovedVideoTitle } from "@/features/workbench/lib/videoWorkflow";
import { markVideoStyleDependentsStale } from "@/features/workbench/lib/invalidateDependents";
import { saveMockDraft, updateMockNodeState, useMockRuntime } from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { requiredItem } from "@/shared/lib/requiredItem";
import { demoProjectId } from "@/shared/data/mockData";

function StyleVisual({ style }: { style: VideoStyle }) {
  return (
    <div className="relative aspect-video overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)]">
      <img
        alt={`${style.name}视觉参考`}
        className="size-full object-cover"
        decoding="async"
        src={style.image}
      />
    </div>
  );
}

export function VideoStyleStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const demo = projectId === demoProjectId || !project;
  const topic = project?.knowledge_point ?? "本课知识点";
  const videoTitle = demo ? demoVideoTitle : getApprovedVideoTitle(runtime, projectId, lessonId);
  const styles = demo ? demoVideoStyles : createTopicVideoStyles(topic);
  const draftKey = `project:${projectId}:lesson:${lessonId}:video-style`;
  const approvedKey = `${draftKey}:approved`;
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:video-style`];
  const approved = nodeState?.status === "approved";
  const stale = nodeState?.status === "stale";
  const currentSaved = runtime.drafts[draftKey]?.value as { selectedId?: string } | undefined;
  const approvedSaved = runtime.drafts[approvedKey]?.value as { selectedId?: string } | undefined;
  const saved = approved ? approvedSaved : (currentSaved ?? approvedSaved);
  const selected =
    styles.find((style) => style.id === saved?.selectedId) ??
    requiredItem(styles, 0, "默认视频风格");
  const [message, setMessage] = useState("");
  const { openContextDrawer } = useWorkbenchUi();
  const selectStyle = (selectedId: string) => {
    saveMockDraft(draftKey, { selectedId }, { lessonId, nodeKey: "video-style", projectId });
    updateMockNodeState(projectId, lessonId, "video-style", {
      stale_reason: null,
      status: "review_required",
      title: "确定画面风格",
    });
  };
  return (
    <WorkbenchPageFrame width="workspace">
      <FocusPageHeader
        action={
          approved ? (
            <Button
              onClick={() => {
                if (!runtime.drafts[approvedKey]) {
                  saveMockDraft(
                    approvedKey,
                    { selectedId: selected.id },
                    { lessonId, nodeKey: "video-style", projectId },
                  );
                }
                updateMockNodeState(projectId, lessonId, "video-style", {
                  stale_reason: null,
                  status: "review_required",
                  title: "确定画面风格",
                });
              }}
              size="md"
              variant="secondary"
            >
              <PencilLine aria-hidden="true" />
              重新选择风格
            </Button>
          ) : (
            <Button
              onClick={() => {
                if (approvedSaved?.selectedId && approvedSaved.selectedId !== selected.id) {
                  markVideoStyleDependentsStale(runtime, projectId, lessonId);
                }
                saveMockDraft(
                  draftKey,
                  { selectedId: selected.id },
                  { lessonId, nodeKey: "video-style", projectId },
                );
                saveMockDraft(
                  approvedKey,
                  { selectedId: selected.id },
                  { lessonId, nodeKey: "video-style", projectId },
                );
                updateMockNodeState(projectId, lessonId, "video-style", {
                  stale_reason: null,
                  status: "approved",
                  title: "确定画面风格",
                });
              }}
              size="md"
            >
              <Check aria-hidden="true" />
              采用这个画面风格
            </Button>
          )
        }
        eyebrow="当前要做：确定视频画面风格"
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : "review_required"} />
        }
        title={`${videoTitle} · 视觉母图`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_260px]">
        <section className="flex min-h-0 items-center justify-center rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-stage)] p-3 md:p-4 lg:max-h-[calc(100dvh-270px)]">
          <div
            className="w-full max-w-[min(960px,max(280px,calc((100dvh-302px)*1.7778)))]"
            data-testid="video-style-preview"
          >
            <StyleVisual style={selected} />
          </div>
        </section>
        <aside className="min-w-0">
          <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">3 种画面风格</p>
          <div className="mt-3 flex w-full max-w-full gap-3 overflow-x-auto pb-1 lg:block lg:space-y-3 lg:overflow-visible lg:pb-0">
            {styles.map((style) => (
              <button
                aria-label={`选择${style.name}`}
                aria-pressed={selected.id === style.id}
                className={`w-40 shrink-0 rounded-[var(--sh-radius-sm)] border bg-[var(--sh-surface-elevated)] p-2 text-left lg:w-full ${selected.id === style.id ? "border-[var(--sh-brand-500)]" : "border-[var(--sh-line-subtle)]"}`}
                key={style.id}
                onClick={() => {
                  selectStyle(style.id);
                  setMessage(`已切换到“${style.name}”`);
                }}
                type="button"
              >
                <StyleVisual style={style} />
                <span className="mt-2 block px-1 text-sm font-semibold text-[var(--sh-ink-strong)]">
                  {style.name}
                </span>
              </button>
            ))}
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-2 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3 text-xs">
            <div>
              <dt className="text-[var(--sh-ink-muted)]">画面</dt>
              <dd className="mt-1 font-semibold text-[var(--sh-ink-strong)]">16:9 · 柔和晨光</dd>
            </div>
            <div>
              <dt className="text-[var(--sh-ink-muted)]">限制</dt>
              <dd className="mt-1 font-semibold text-[var(--sh-ink-strong)]">无文字与水印</dd>
            </div>
          </dl>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button onClick={() => openContextDrawer("prompt")} size="sm" variant="secondary">
              提出修改
            </Button>
            <Button
              onClick={() => {
                const index = styles.findIndex((style) => style.id === selected.id);
                const next = requiredItem(styles, (index + 1) % styles.length, "下一种视频风格");
                selectStyle(next.id);
                setMessage("已生成并切换到新的画面风格");
              }}
              size="sm"
              variant="quiet"
            >
              <RefreshCw aria-hidden="true" />
              重新生成
            </Button>
          </div>
        </aside>
      </div>
      {message ? (
        <p className="mt-3 text-sm font-medium text-[var(--sh-success)]" role="status">
          {message}
        </p>
      ) : null}
    </WorkbenchPageFrame>
  );
}
