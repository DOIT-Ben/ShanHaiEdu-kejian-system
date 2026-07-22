import { ArrowRight, Check, Clock3, GripVertical, Image, PencilLine, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import {
  createTopicStoryBeats,
  demoStoryBeats,
  demoVideoTitle,
  type VideoStoryBeat,
} from "@/features/workbench/lib/videoContent";
import { createStoryBeatsFromApprovedMaster } from "@/features/workbench/lib/videoWorkflow";
import { markRoughStoryboardDependentsStale } from "@/features/workbench/lib/invalidateDependents";
import { saveMockDraft, updateMockNodeState, useMockRuntime } from "@/shared/api/mockClient";
import { reorderItem } from "@/shared/lib/reorderItem";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { demoProjectId } from "@/shared/data/mockData";

export function RoughStoryboardStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const demo = projectId === demoProjectId || !project;
  const topic = project?.knowledge_point ?? "本课知识点";
  const approvedMasterBeats = createStoryBeatsFromApprovedMaster(runtime, projectId, lessonId);
  const defaultBeats = demo
    ? demoStoryBeats
    : (approvedMasterBeats ?? createTopicStoryBeats(topic));
  const draftKey = `project:${projectId}:lesson:${lessonId}:rough-storyboard`;
  const approvedKey = `${draftKey}:approved`;
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:rough-storyboard`];
  const stale = nodeState?.status === "stale";
  const currentStored = runtime.drafts[draftKey]?.value as
    { approved?: boolean; items?: VideoStoryBeat[] } | undefined;
  const approvedStored = runtime.drafts[approvedKey]?.value as
    { approved?: boolean; items?: VideoStoryBeat[] } | undefined;
  const stored =
    nodeState?.status === "approved" ? approvedStored : (currentStored ?? approvedStored);
  const [approved, setApproved] = useState(stored?.approved === true);
  const confirmed = approved && nodeState?.status === "approved";
  const [items, setItems] = useState<VideoStoryBeat[]>(() =>
    Array.isArray(stored?.items) && stored.items.length > 0 ? stored.items : defaultBeats,
  );
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [reorderMessage, setReorderMessage] = useState("");
  const persist = (nextItems: VideoStoryBeat[], nextApproved: boolean) => {
    if (!nextApproved && nodeState?.status === "approved" && !approvedStored) {
      saveMockDraft(
        approvedKey,
        { approved: true, items },
        { lessonId, nodeKey: "rough-storyboard", projectId },
      );
    }
    if (
      nextApproved &&
      Array.isArray(approvedStored?.items) &&
      JSON.stringify(approvedStored.items) !== JSON.stringify(nextItems)
    ) {
      markRoughStoryboardDependentsStale(runtime, projectId, lessonId);
    }
    setItems(nextItems);
    setApproved(nextApproved);
    saveMockDraft(
      draftKey,
      { approved: nextApproved, items: nextItems },
      { lessonId, nodeKey: "rough-storyboard", projectId },
    );
    if (nextApproved) {
      saveMockDraft(
        approvedKey,
        { approved: true, items: nextItems },
        { lessonId, nodeKey: "rough-storyboard", projectId },
      );
    }
    updateMockNodeState(projectId, lessonId, "rough-storyboard", {
      stale_reason: null,
      status: nextApproved ? "approved" : "review_required",
      title: "安排故事镜头",
    });
  };
  const moveBeat = (from: number, to: number) => {
    if (from === to || to < 0 || to >= items.length) return;
    persist(reorderItem(items, from, to), false);
    setReorderMessage(`已将故事节拍移到第 ${String(to + 1)} 位`);
  };
  return (
    <WorkbenchPageFrame width="wide">
      <FocusPageHeader
        action={
          confirmed ? (
            <>
              <Button onClick={() => persist(items, false)} size="md" variant="secondary">
                <PencilLine aria-hidden="true" />
                重新安排镜头
              </Button>
              <Button asChild size="md">
                <Link to={`/app/projects/${projectId}/lessons/${lessonId}/work/video-style`}>
                  确定画面风格
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </>
          ) : (
            <Button onClick={() => persist(items, true)} size="lg">
              <Check aria-hidden="true" />
              {stale ? "重新确认故事镜头" : "确认故事镜头"}
            </Button>
          )
        }
        eyebrow="当前要做：安排故事镜头"
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : confirmed ? "approved" : "review_required"} />
        }
        title={`${demo ? demoVideoTitle : topic} · ${String(items.length)} 个故事节拍`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-4 pb-4">
        <div className="grid items-stretch gap-3 md:grid-cols-2 xl:grid-cols-5">
          {items.map((beat, index) => (
            <article
              className="relative flex min-w-0 flex-col rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3"
              key={beat.title}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => {
                if (dragIndex !== null) moveBeat(dragIndex, index);
                setDragIndex(null);
              }}
            >
              <div className="absolute -left-2 top-5 grid size-6 place-items-center rounded-full bg-[var(--sh-brand-700)] text-xs font-bold text-white">
                {index + 1}
              </div>
              <button
                aria-label={`拖动${beat.title}；也可使用左右方向键移动`}
                className="ml-auto grid size-9 place-items-center rounded-md text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)]"
                disabled={confirmed}
                draggable
                onDragStart={() => setDragIndex(index)}
                onKeyDown={(event) => {
                  if (event.key === "ArrowLeft") {
                    event.preventDefault();
                    moveBeat(index, index - 1);
                  }
                  if (event.key === "ArrowRight") {
                    event.preventDefault();
                    moveBeat(index, index + 1);
                  }
                }}
                type="button"
              >
                <GripVertical aria-hidden="true" className="size-4" />
              </button>
              <p className="mt-2 flex items-center gap-1 text-xs font-semibold text-[var(--sh-brand-600)]">
                <Clock3 aria-hidden="true" className="size-3.5" />
                {beat.time}
              </p>
              <h2 className="mt-3 font-semibold text-[var(--sh-ink-strong)]">{beat.title}</h2>
              <textarea
                aria-label={`${beat.title}主要事件`}
                className="mt-3 min-h-20 flex-1 resize-none rounded-[var(--sh-radius-sm)] border border-transparent bg-[var(--sh-surface-soft)] p-2 text-sm leading-5 outline-none focus:border-[var(--sh-brand-500)] focus:bg-[var(--sh-surface-elevated)]"
                disabled={confirmed}
                onChange={(event) =>
                  persist(
                    items.map((item, itemIndex) =>
                      itemIndex === index ? { ...item, event: event.target.value } : item,
                    ),
                    false,
                  )
                }
                value={beat.event}
              />
              <p className="mt-3 flex items-start gap-1.5 text-xs leading-5 text-[var(--sh-ink-muted)]">
                <Image aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
                {beat.assets}
              </p>
            </article>
          ))}
        </div>
      </div>
      <p aria-live="polite" className="sr-only">
        {reorderMessage}
      </p>
      {!confirmed ? (
        <button
          className="inline-flex min-h-11 items-center gap-2 rounded-[var(--sh-radius-sm)] border border-dashed border-[var(--sh-line-strong)] px-4 text-sm font-semibold text-[var(--sh-brand-600)] hover:bg-[var(--sh-brand-50)]"
          onClick={() =>
            persist(
              [
                ...items,
                {
                  time: "待安排",
                  title: `新增故事节拍 ${String(items.length + 1)}`,
                  event: `补充这个节拍中与${demo ? demoVideoTitle : topic}有关的主要事件。`,
                  assets: "待补充资产",
                },
              ],
              false,
            )
          }
          type="button"
        >
          <Plus aria-hidden="true" className="size-4" />
          增加故事节拍
        </button>
      ) : null}
    </WorkbenchPageFrame>
  );
}
