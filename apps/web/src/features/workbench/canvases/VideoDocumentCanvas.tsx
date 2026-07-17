import { Link } from "react-router";
import { Play } from "lucide-react";
import { useArtifactVersion, useNodeRunDetail, useStartNode } from "@/features/node-runs";
import { ApprovalActions } from "@/features/approvals";
import { PromptSection } from "@/features/prompt-editing";
import { Button, Skeleton, toast } from "@/shared/ui";
import { useStepNodeRun, useWorkbench } from "../context";
import { FailedPanel, RunningPanel, StepScaffold, StaleBanner } from "../parts";

/**
 * 通用文本节点画布：母版剧本 / 故事镜头等以文档形式确认的视频节点。
 * 内容为通用键值块渲染（快照隔离：只依赖选中的导入方案）。
 */
export function VideoDocumentCanvas({
  title,
  description,
  notReadyHint,
  runningLabel,
}: {
  title: string;
  description: string;
  notReadyHint: string;
  runningLabel: string;
}) {
  const { projectId, lessonId } = useWorkbench();
  const { nodeRun, isPending } = useStepNodeRun();
  const { data: detail } = useNodeRunDetail(nodeRun?.id ?? null);
  const start = useStartNode(nodeRun?.id ?? "");
  const versionId = detail?.node_run.current_artifact_version_id ?? null;
  const { data: artifact } = useArtifactVersion(versionId);

  if (isPending || !nodeRun) {
    return <Skeleton className="m-6 h-96 rounded-lg" />;
  }

  const status = detail?.node_run.status ?? nodeRun.status;
  const canStart = status === "ready" || status === "failed";

  const startGeneration = () =>
    start.mutate(undefined, {
      onError: (error) => toast({ tone: "danger", title: "无法开始", description: error.message }),
    });

  return (
    <StepScaffold
      title={title}
      description={description}
      status={status}
      primaryAction={
        canStart ? (
          <Button onClick={startGeneration} loading={start.isPending} loadingText="正在开始…">
            <Play className="size-4" aria-hidden />
            开始生成
          </Button>
        ) : status === "review_required" && versionId ? (
          <ApprovalActions
            versionId={versionId}
            nodeRunId={nodeRun.id}
            validationIssues={artifact?.version.validation_issues ?? []}
          />
        ) : undefined
      }
    >
      {status === "stale" ? <StaleBanner nodeRun={detail?.node_run ?? nodeRun} /> : null}
      {status === "queued" || status === "running" ? (
        <RunningPanel job={detail?.active_job ?? null} label={runningLabel} />
      ) : status === "failed" ? (
        <FailedPanel
          message={detail?.active_job?.error?.message ?? "生成失败。"}
          onRetry={startGeneration}
          retrying={start.isPending}
        />
      ) : status === "not_ready" || status === "disabled" ? (
        <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
          {notReadyHint}
          {status === "not_ready" ? (
            <Link
              to={`/app/projects/${projectId}/lessons/${lessonId}/work/intro-selection`}
              className="ml-1 font-medium text-brand-600 hover:underline"
            >
              去选择导入方案
            </Link>
          ) : null}
        </p>
      ) : (
        <div className="mx-auto max-w-3xl space-y-5">
          {artifact ? (
            <article className="sh-paper-canvas rounded-lg border border-line-subtle p-8 shadow-card">
              <DocumentContent content={artifact.version.content} />
            </article>
          ) : null}
          <PromptSection nodeRunId={nodeRun.id} />
        </div>
      )}
    </StepScaffold>
  );
}

/** 通用内容块渲染：对象 → 分节；数组 → 编号列表；标量 → 段落。 */
function DocumentContent({ content, depth = 0 }: { content: unknown; depth?: number }) {
  if (content == null) return null;
  if (typeof content === "string" || typeof content === "number" || typeof content === "boolean") {
    return <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">{String(content)}</p>;
  }
  if (Array.isArray(content)) {
    return (
      <ol className="space-y-3">
        {content.map((item, index) => (
          <li key={index} className="rounded-md bg-surface-soft/70 p-3">
            <p className="text-xs font-semibold text-brand-600">{index + 1}</p>
            <div className="mt-1">
              <DocumentContent content={item} depth={depth + 1} />
            </div>
          </li>
        ))}
      </ol>
    );
  }
  const record = content as Record<string, unknown>;
  return (
    <div className={depth === 0 ? "space-y-6" : "space-y-3"}>
      {Object.entries(record).map(([key, value]) => (
        <section key={key}>
          <h3 className={depth === 0 ? "text-base font-semibold text-ink-strong" : "text-sm font-medium text-ink-strong"}>
            {KEY_LABELS[key] ?? key}
          </h3>
          <div className="mt-1.5">
            <DocumentContent content={value} depth={depth + 1} />
          </div>
        </section>
      ))}
    </div>
  );
}

const KEY_LABELS: Record<string, string> = {
  title: "标题",
  logline: "一句话概述",
  theme: "主题",
  characters: "角色",
  name: "名字",
  role: "角色定位",
  description: "描述",
  scenes: "场景",
  scene_title: "场景",
  narration: "旁白",
  visual: "画面",
  dialogue: "台词",
  duration_seconds: "时长（秒）",
  shots: "镜头",
  shot_title: "镜头",
  summary: "概述",
  camera: "镜头运动",
  audio: "声音",
  emotional_beat: "情绪节拍",
  handoff: "交接",
  hook: "开场钩子",
  question: "问题",
  style: "风格",
  notes: "备注",
};
