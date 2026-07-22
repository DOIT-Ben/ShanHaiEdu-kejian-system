import * as Dialog from "@radix-ui/react-dialog";
import { ArrowRight, RefreshCw, X } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
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
import { saveMockDraft, updateMockNodeState, useMockRuntime } from "@/shared/api/mockClient";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { IconButton } from "@/shared/ui/IconButton";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { SelectableCard } from "@/shared/ui/SelectableCard";
import { requiredItem } from "@/shared/lib/requiredItem";
import { demoProjectId } from "@/shared/data/mockData";

function StyleVisual({
  loading = "eager",
  style,
}: {
  loading?: "eager" | "lazy";
  style: VideoStyle;
}) {
  return (
    <div className="relative aspect-video overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)]">
      <img
        alt={`${style.name}视觉参考`}
        className="size-full object-cover"
        decoding="async"
        loading={loading}
        src={style.image}
      />
    </div>
  );
}

export function VideoStyleStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const navigate = useNavigate();
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
  const [redesignOpen, setRedesignOpen] = useState(false);
  const [redesignRequest, setRedesignRequest] = useState("");
  const selectStyle = (selectedId: string) => {
    saveMockDraft(draftKey, { selectedId }, { lessonId, nodeKey: "video-style", projectId });
    updateMockNodeState(projectId, lessonId, "video-style", {
      stale_reason: null,
      status: "review_required",
      title: "确定画面风格",
    });
  };
  const confirmAndContinue = () => {
    if (!approved) {
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
    }
    void navigate(`/app/projects/${projectId}/lessons/${lessonId}/work/video-asset-plan`);
  };
  return (
    <WorkbenchPageFrame width="workspace">
      <FocusPageHeader
        action={
          <Button onClick={confirmAndContinue} size="md">
            制作镜头图片
            <ArrowRight aria-hidden="true" />
          </Button>
        }
        eyebrow="当前要做：确定视频画面风格"
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : "review_required"} />
        }
        title={`${videoTitle} · 视觉母图`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div
        className="mt-3 grid items-start gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]"
        data-layout="split-preview"
      >
        <section className="flex min-h-0 items-center justify-center rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-stage)] p-3 md:p-4">
          <div className="w-full max-w-[720px]" data-testid="video-style-preview">
            <StyleVisual style={selected} />
          </div>
        </section>
        <aside className="flex w-full min-w-0 flex-col">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <div>
              <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">选择画面风格</p>
              <p className="mt-0.5 text-xs text-[var(--sh-ink-muted)]">
                {approved ? `当前采用：${selected.name}` : `已选中：${selected.name}`}
              </p>
            </div>
            <span className="text-xs font-medium text-[var(--sh-ink-muted)]">3 种风格</span>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 md:gap-3">
            {styles.map((style) => {
              const previewing = selected.id === style.id;
              return (
                <SelectableCard
                  aria-label={`选择${style.name}`}
                  className="p-1.5 md:p-2"
                  key={style.id}
                  onClick={() => {
                    selectStyle(style.id);
                    setMessage(`已选择“${style.name}”`);
                  }}
                  selected={previewing}
                >
                  <StyleVisual loading="lazy" style={style} />
                  <span
                    className={`mt-1.5 block truncate px-1 text-xs font-semibold ${previewing ? "text-[var(--sh-brand-700)]" : "text-[var(--sh-ink-strong)]"}`}
                  >
                    {style.name}
                  </span>
                </SelectableCard>
              );
            })}
          </div>
          <div className="mt-3 flex flex-wrap gap-2 border-t border-[var(--sh-line-subtle)] pt-3">
            <Button onClick={() => setRedesignOpen(true)} size="sm" variant="secondary">
              重新设计画面
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
              换一组风格
            </Button>
          </div>
          <p aria-live="polite" className="sr-only" role="status">
            {message}
          </p>
        </aside>
      </div>
      <Dialog.Root onOpenChange={setRedesignOpen} open={redesignOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-[var(--sh-overlay-scrim)] backdrop-blur-[1px]" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,600px)] -translate-x-1/2 -translate-y-1/2 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-floating)] sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <Dialog.Title className="text-lg font-semibold text-[var(--sh-ink-strong)]">
                  重新设计画面
                </Dialog.Title>
                <Dialog.Description className="mt-1 text-sm leading-6 text-[var(--sh-ink-muted)]">
                  说清想保留或改变的部分，新的候选会在当前画面风格基础上生成。
                </Dialog.Description>
              </div>
              <Dialog.Close asChild>
                <IconButton label="关闭">
                  <X aria-hidden="true" />
                </IconButton>
              </Dialog.Close>
            </div>
            <label className="mt-5 block">
              <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">调整画面</span>
              <textarea
                className="mt-2 min-h-32 w-full resize-y rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-paper)] p-3 text-sm leading-6 outline-none focus:border-[var(--sh-brand-500)] focus:shadow-[var(--sh-shadow-focus)]"
                onChange={(event) => setRedesignRequest(event.target.value)}
                placeholder="例如：保留暖色纸艺质感，拉开人物与果汁瓶的距离，让学生能看清比较对象。"
                value={redesignRequest}
              />
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button variant="quiet">取消</Button>
              </Dialog.Close>
              <Button
                disabled={!redesignRequest.trim()}
                onClick={() => {
                  const index = styles.findIndex((style) => style.id === selected.id);
                  const next = requiredItem(styles, (index + 1) % styles.length, "下一种视频风格");
                  saveMockDraft(`${draftKey}:redesign-request`, redesignRequest.trim(), {
                    lessonId,
                    nodeKey: "video-style:redesign-request",
                    projectId,
                  });
                  selectStyle(next.id);
                  setMessage("已按新要求生成一组画面风格");
                  setRedesignRequest("");
                  setRedesignOpen(false);
                }}
              >
                按要求重新设计
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </WorkbenchPageFrame>
  );
}
