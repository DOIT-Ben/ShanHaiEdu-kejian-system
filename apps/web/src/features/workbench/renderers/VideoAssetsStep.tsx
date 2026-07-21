import { ArrowRight, CheckCircle2, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getDemoVideoSceneSource } from "@/features/home/components/VideoScenePreview";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import {
  createTopicVideoAssets,
  demoVideoAssets,
  demoVideoTitle,
} from "@/features/workbench/lib/videoContent";
import {
  createAssetsFromApprovedStory,
  getApprovedVideoStyle,
} from "@/features/workbench/lib/videoWorkflow";
import { saveMockDraft, useMockRuntime } from "@/shared/api/mocks/runtime";
import { Button, buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { demoProjectId } from "@/shared/data/mockData";

export function VideoAssetsStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const demo = projectId === demoProjectId || !project;
  const topic = project?.knowledge_point ?? "本课知识点";
  const approvedStoryAssets = createAssetsFromApprovedStory(runtime, projectId, lessonId);
  const approvedStyleId = getApprovedVideoStyle(runtime, projectId, lessonId)?.selectedId;
  const approvedStyleLabel =
    approvedStyleId === "clay" ? "柔和定格" : approvedStyleId === "clean" ? "清透插画" : "纸艺课堂";
  const assets = demo ? demoVideoAssets : (approvedStoryAssets ?? createTopicVideoAssets(topic));
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:video-assets`];
  const approved = nodeState?.status === "approved";
  const stale = nodeState?.status === "stale";
  const readyCount = approved
    ? assets.length
    : assets.filter((asset) => asset.status === "ready").length;
  const pendingCount = assets.length - readyCount;
  const [message, setMessage] = useState("");
  return (
    <WorkbenchPageFrame>
      <FocusPageHeader
        action={
          approved ? (
            <Link
              className={buttonVariants({ size: "md" })}
              to={`/app/projects/${projectId}/lessons/${lessonId}/work/fine-storyboard`}
            >
              选择关键帧参考
              <ArrowRight aria-hidden="true" />
            </Link>
          ) : (
            <Link
              className={buttonVariants({ size: "lg" })}
              to={`/app/creation/batches/video-assets-${projectId}--lesson--${lessonId}?sourceProjectId=${encodeURIComponent(projectId)}&lessonId=${encodeURIComponent(lessonId)}`}
            >
              开始制作镜头图片
              <ArrowRight aria-hidden="true" />
            </Link>
          )
        }
        eyebrow="当前要做：准备视频所需图片"
        hideEyebrow
        status={
          <StatusBadge
            status={
              stale
                ? "stale"
                : approved
                  ? "approved"
                  : pendingCount === 0
                    ? "ready"
                    : "review_required"
            }
          />
        }
        title={`${demo ? demoVideoTitle : topic} · ${String(assets.length)} 类图片资产`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {assets.map((asset, index) => (
          <article
            className="overflow-hidden rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3"
            key={asset.id}
          >
            <div className="relative aspect-video overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)]">
              <img
                alt={
                  demo
                    ? `${asset.title}参考画面`
                    : `果汁标签课堂示例，作为“${asset.title}”的构图参考，不是当前课题生成结果`
                }
                className="size-full object-cover"
                decoding="async"
                loading="lazy"
                src={getDemoVideoSceneSource(index)}
              />
              {!demo ? (
                <span className="absolute bottom-2 left-2 rounded-full bg-[var(--sh-surface-elevated)]/92 px-2 py-1 text-[10px] font-semibold text-[var(--sh-brand-700)] shadow-[var(--sh-shadow-card)] backdrop-blur-sm">
                  示例构图 · 等待当前课题素材
                </span>
              ) : null}
              {approved || asset.status === "ready" ? (
                <span className="absolute right-2 top-2 flex items-center gap-1 rounded-full bg-[var(--sh-surface-elevated)]/92 px-2 py-1 text-xs font-semibold text-[var(--sh-success)] shadow-[var(--sh-shadow-card)] backdrop-blur-sm">
                  <CheckCircle2 aria-hidden="true" className="size-4" />
                  {demo ? "已准备" : "清单已准备"}
                </span>
              ) : (
                <span className="absolute right-2 top-2">
                  <StatusBadge status="not_ready" />
                </span>
              )}
            </div>
            <p className="mt-3 text-xs font-semibold text-[var(--sh-brand-600)]">{asset.type}</p>
            <h2 className="mt-1 font-semibold text-[var(--sh-ink-strong)]">{asset.title}</h2>
            <p className="mt-2 text-sm text-[var(--sh-ink-muted)]">
              来源：故事节拍 {Math.min(index + 1, 5)} · {approvedStyleLabel}
            </p>
          </article>
        ))}
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <Button
          onClick={() => {
            saveMockDraft(
              `project:${projectId}:lesson:${lessonId}:video-assets-check`,
              {
                checkedAt: new Date().toISOString(),
                ready: readyCount,
                required: assets.length,
              },
              { lessonId, nodeKey: "video-assets", projectId },
            );
            setMessage(
              `资产清单已重新检查：${String(readyCount)} 类已准备，${String(pendingCount)} 类等待生成。`,
            );
          }}
          variant="secondary"
        >
          <RefreshCw aria-hidden="true" />
          重新检查资产清单
        </Button>
      </div>
      {message ? (
        <p className="mt-3 text-sm font-medium text-[var(--sh-success)]" role="status">
          {message}
        </p>
      ) : null}
    </WorkbenchPageFrame>
  );
}
