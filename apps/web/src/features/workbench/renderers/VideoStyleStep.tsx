import * as Dialog from "@radix-ui/react-dialog";
import { ArrowRight, Check, PencilLine, RefreshCw, X } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
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
import { IconButton } from "@/shared/ui/IconButton";
import { StatusBadge } from "@/shared/ui/StatusBadge";
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
  return (
    <WorkbenchPageFrame width="workspace">
      <FocusPageHeader
        action={
          approved ? (
            <>
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
              <Button asChild size="md">
                <Link to={`/app/projects/${projectId}/lessons/${lessonId}/work/video-assets`}>
                  制作镜头图片
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </>
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
      <div className="mt-3 space-y-3">
        <section className="flex min-h-0 items-center justify-center rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-stage)] p-3 md:p-4">
          <div
            className="w-full max-w-[min(960px,max(280px,calc((100dvh-450px)*1.7778)))]"
            data-testid="video-style-preview"
          >
            <StyleVisual style={selected} />
          </div>
        </section>
        <aside className="mx-auto w-full max-w-[720px]">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <div>
              <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">选择画面风格</p>
              <p className="mt-0.5 text-xs text-[var(--sh-ink-muted)]">
                {approved
                  ? `已采用：${selected.name}`
                  : `点击候选查看大图 · 当前预览：${selected.name}`}
              </p>
            </div>
            <span className="text-xs font-medium text-[var(--sh-ink-muted)]">3 种风格</span>
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 md:gap-3">
            {styles.map((style) => {
              const previewing = selected.id === style.id;
              return (
                <button
                  aria-label={`选择${style.name}`}
                  aria-pressed={previewing}
                  className={`group relative min-w-0 rounded-[var(--sh-radius-sm)] border bg-[var(--sh-surface-elevated)] p-1.5 text-left transition-[border-color,box-shadow,transform] motion-reduce:transition-none md:p-2 ${previewing ? "border-[var(--sh-brand-600)] bg-[var(--sh-brand-50)] shadow-[var(--sh-shadow-card)] ring-1 ring-[var(--sh-brand-200)]" : "border-[var(--sh-line-subtle)] hover:-translate-y-0.5 hover:border-[var(--sh-brand-300)] hover:shadow-[var(--sh-shadow-card)]"} focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sh-brand-500)] focus-visible:ring-offset-2 disabled:cursor-default disabled:opacity-85`}
                  disabled={approved}
                  key={style.id}
                  onClick={() => {
                    selectStyle(style.id);
                    setMessage(`正在预览“${style.name}”`);
                  }}
                  type="button"
                >
                  <StyleVisual loading="lazy" style={style} />
                  {previewing ? (
                    <span className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-700)] px-1.5 py-1 text-[10px] font-semibold text-white shadow-[var(--sh-shadow-card)]">
                      <Check aria-hidden="true" className="size-3" />
                      当前预览
                    </span>
                  ) : (
                    <span className="pointer-events-none absolute inset-x-2 bottom-7 grid min-h-8 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-overlay-scrim)] px-2 text-xs font-semibold text-white opacity-0 transition-opacity group-hover:opacity-100 motion-reduce:transition-none">
                      预览这张
                    </span>
                  )}
                  <span
                    className={`mt-1.5 block truncate px-1 text-xs font-semibold ${previewing ? "text-[var(--sh-brand-700)]" : "text-[var(--sh-ink-strong)]"}`}
                  >
                    {style.name}
                  </span>
                </button>
              );
            })}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              disabled={approved}
              onClick={() => setRedesignOpen(true)}
              size="sm"
              variant="secondary"
            >
              重新设计画面
            </Button>
            <Button
              disabled={approved}
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
