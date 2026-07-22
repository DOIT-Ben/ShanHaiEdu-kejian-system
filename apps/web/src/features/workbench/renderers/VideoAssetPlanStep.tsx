import { ArrowRight, Check, Layers3 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import {
  createAssetsFromApprovedStory,
  createShotsFromApprovedStory,
} from "@/features/workbench/lib/videoWorkflow";
import {
  createTopicVideoAssets,
  createTopicVideoShots,
} from "@/features/workbench/lib/videoContent";
import {
  saveMockDraft,
  updateMockNodeState,
  useMockRuntime,
  type MockRuntimeState,
} from "@/shared/api/mockClient";
import { Button, buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";

export type PlannedVideoImage = {
  id: string;
  prompt: string;
  scope: "common" | "shot";
  source: string;
  title: string;
  type: string;
};

function buildPlan(runtime: MockRuntimeState, projectId: string, lessonId: string) {
  const project = runtime.projects.find((item) => item.id === projectId);
  const topic = project?.knowledge_point ?? "本课知识点";
  const assets =
    createAssetsFromApprovedStory(runtime, projectId, lessonId) ?? createTopicVideoAssets(topic);
  const shots =
    createShotsFromApprovedStory(runtime, projectId, lessonId) ?? createTopicVideoShots(topic);
  const common: PlannedVideoImage[] = assets
    .filter((asset) => asset.id !== "keyframe")
    .map((asset) => ({
      id: `common-${asset.id}`,
      prompt: `为“${topic}”课堂导入视频设计${asset.type}资产“${asset.title}”。单一主体，16:9，继承已确认视觉母图的材质、光线和配色；不出现水印、Logo、乱码或准确文字数字。`,
      scope: "common",
      source: "母版剧本与粗分镜去重清单",
      title: asset.title,
      type: asset.type,
    }));
  const shotItems: PlannedVideoImage[] = shots.map((shot, index) => ({
    id: `shot-${String(index + 1)}`,
    prompt: `制作${shot.id}的镜头内部场景图：${shot.beat}。构图为${shot.movement}的起始关键帧，保留动作发展和镜头衔接空间，人物、场景、道具与通用资产保持一致。`,
    scope: "shot",
    source: `${shot.id} · ${String(shot.duration)} 秒`,
    title: `${shot.id} · ${shot.beat}`,
    type: "分镜内部图",
  }));
  return [...common, ...shotItems];
}

export function VideoAssetPlanStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const draftKey = `project:${projectId}:lesson:${lessonId}:video-asset-plan`;
  const approvedKey = `${draftKey}:approved`;
  const saved = runtime.drafts[draftKey]?.value as PlannedVideoImage[] | undefined;
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:video-asset-plan`];
  const initialPlan = useMemo(
    () => saved ?? buildPlan(runtime, projectId, lessonId),
    [lessonId, projectId, runtime, saved],
  );
  const [items, setItems] = useState(initialPlan);
  const approved = nodeState?.status === "approved";
  const stale = nodeState?.status === "stale";
  const commonCount = items.filter((item) => item.scope === "common").length;
  const shotCount = items.length - commonCount;

  const approve = () => {
    saveMockDraft(draftKey, items, { lessonId, nodeKey: "video-asset-plan", projectId });
    saveMockDraft(approvedKey, items, { lessonId, nodeKey: "video-asset-plan", projectId });
    updateMockNodeState(projectId, lessonId, "video-asset-plan", {
      stale_reason: null,
      status: "approved",
      title: "规划图片资产",
    });
  };

  return (
    <WorkbenchPageFrame width="workspace">
      <FocusPageHeader
        action={
          approved ? (
            <Link
              className={buttonVariants({ size: "md" })}
              to={`/app/projects/${projectId}/lessons/${lessonId}/work/video-assets`}
            >
              制作镜头图片
              <ArrowRight aria-hidden="true" />
            </Link>
          ) : (
            <Button onClick={approve} size="md">
              <Check aria-hidden="true" />
              确认资产规划
            </Button>
          )
        }
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : "review_required"} />
        }
        title={`${String(commonCount)} 项通用资产 · ${String(shotCount)} 项分镜资产`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {(["common", "shot"] as const).map((scope) => (
          <section aria-label={scope === "common" ? "通用图片资产" : "分镜内部图片"} key={scope}>
            <div className="mb-2 flex items-center gap-2">
              <Layers3 aria-hidden="true" className="size-4 text-[var(--sh-brand-600)]" />
              <h2 className="font-semibold text-[var(--sh-ink-strong)]">
                {scope === "common" ? "通用图片资产" : "分镜内部图片"}
              </h2>
            </div>
            <div className="grid gap-2">
              {items
                .filter((item) => item.scope === scope)
                .map((item) => (
                  <article
                    className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3"
                    key={item.id}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-[var(--sh-brand-600)]">
                          {item.type}
                        </p>
                        <h3 className="mt-0.5 font-semibold text-[var(--sh-ink-strong)]">
                          {item.title}
                        </h3>
                      </div>
                      <span className="shrink-0 text-xs text-[var(--sh-ink-muted)]">
                        {item.source}
                      </span>
                    </div>
                    <textarea
                      aria-label={`${item.title}提示词`}
                      className="mt-2 min-h-24 w-full resize-y rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-paper)] p-2.5 text-sm leading-6 text-[var(--sh-ink-default)] outline-none focus:border-[var(--sh-brand-500)] focus:shadow-[var(--sh-shadow-focus)] disabled:opacity-75"
                      disabled={approved}
                      onChange={(event) =>
                        setItems((current) =>
                          current.map((candidate) =>
                            candidate.id === item.id
                              ? { ...candidate, prompt: event.target.value }
                              : candidate,
                          ),
                        )
                      }
                      value={item.prompt}
                    />
                  </article>
                ))}
            </div>
          </section>
        ))}
      </div>
    </WorkbenchPageFrame>
  );
}
