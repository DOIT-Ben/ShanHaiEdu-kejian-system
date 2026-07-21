import { ArrowRight, CheckCircle2, Clock3, ImagePlus } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import {
  createTopicVideoAssets,
  createTopicVideoShots,
} from "@/features/workbench/lib/videoContent";
import {
  createAssetsFromApprovedStory,
  createShotsFromApprovedStory,
} from "@/features/workbench/lib/videoWorkflow";
import { useMockRuntime } from "@/shared/api/mocks/runtime";
import { listMockSavedResults } from "@/shared/api/mocks/savedResults";
import { buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";

export function VideoAssetsStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const topic = project?.knowledge_point ?? "本课知识点";
  const commonAssets =
    createAssetsFromApprovedStory(runtime, projectId, lessonId) ?? createTopicVideoAssets(topic);
  const shots =
    createShotsFromApprovedStory(runtime, projectId, lessonId) ?? createTopicVideoShots(topic);
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:video-assets`];
  const approved = nodeState?.status === "approved";
  const stale = nodeState?.status === "stale";
  const savedResults = listMockSavedResults(runtime, projectId).filter((item) =>
    item.slotKey.startsWith(`video.asset.${lessonId}.`),
  );
  const total = commonAssets.filter((item) => item.id !== "keyframe").length + shots.length;
  const completed = approved ? total : Math.min(savedResults.length, total);

  return (
    <WorkbenchPageFrame width="workspace">
      <FocusPageHeader
        action={
          approved ? (
            <Link
              className={buttonVariants({ size: "md" })}
              to={`/app/projects/${projectId}/lessons/${lessonId}/work/fine-storyboard`}
            >
              设计视频分镜提示词
              <ArrowRight aria-hidden="true" />
            </Link>
          ) : (
            <Link
              className={buttonVariants({ size: "md" })}
              to={`/app/creation/images?projectId=${encodeURIComponent(projectId)}&lessonId=${encodeURIComponent(lessonId)}&package=video-assets`}
            >
              <ImagePlus aria-hidden="true" />
              进入图片创作台
            </Link>
          )
        }
        hideEyebrow
        status={
          <StatusBadge
            status={
              stale
                ? "stale"
                : approved
                  ? "approved"
                  : completed > 0
                    ? "partially_completed"
                    : "ready"
            }
          />
        }
        title={`镜头图片制作 · ${String(completed)}/${String(total)}`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <section
        aria-label="图片资产制作状态"
        className="mt-4 overflow-hidden border-y border-[var(--sh-line-subtle)]"
      >
        {[
          ...commonAssets.filter((item) => item.id !== "keyframe"),
          ...shots.map((shot, index) => ({
            id: `shot-${String(index + 1)}`,
            status: "needs_generation" as const,
            title: `${shot.id} · ${shot.beat}`,
            type: "分镜内部图",
          })),
        ].map((item, index) => {
          const ready = approved || index < completed;
          return (
            <article
              className="grid min-h-14 items-center gap-2 border-b border-[var(--sh-line-subtle)] px-2 py-2 last:border-b-0 sm:grid-cols-[32px_minmax(0,1fr)_120px]"
              key={item.id}
            >
              <span
                className={`grid size-8 place-items-center rounded-[var(--sh-radius-sm)] ${ready ? "bg-[var(--sh-success-soft)] text-[var(--sh-success-strong)]" : "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-muted)]"}`}
              >
                {ready ? (
                  <CheckCircle2 aria-hidden="true" className="size-4" />
                ) : (
                  <Clock3 aria-hidden="true" className="size-4" />
                )}
              </span>
              <div className="min-w-0">
                <p className="truncate font-medium text-[var(--sh-ink-strong)]">{item.title}</p>
                <p className="text-xs text-[var(--sh-ink-muted)]">{item.type}</p>
              </div>
              <span
                className={`text-xs font-semibold sm:text-right ${ready ? "text-[var(--sh-success-strong)]" : "text-[var(--sh-ink-muted)]"}`}
              >
                {ready ? "已保存到项目" : "等待制作"}
              </span>
            </article>
          );
        })}
      </section>
    </WorkbenchPageFrame>
  );
}
