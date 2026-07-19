import {
  Check,
  Download,
  FileCheck2,
  LoaderCircle,
  Music,
  PencilLine,
  RotateCcw,
  Subtitles,
  Volume2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { VideoScenePreview } from "@/features/home/components/VideoScenePreview";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { demoVideoTitle } from "@/features/workbench/lib/videoContent";
import {
  getApprovedFineStoryboard,
  getApprovedVideoStyle,
  getApprovedVideoTitle,
} from "@/features/workbench/lib/videoWorkflow";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import {
  createMockTask,
  saveMockDraft,
  updateMockNodeState,
  useMockRuntime,
} from "@/shared/api/mocks/runtime";
import { downloadExampleFile } from "@/shared/lib/downloadExampleFile";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { demoProjectId } from "@/shared/data/mockData";

function settledTaskStatus(status: string) {
  if (status === "failed") return "failed" as const;
  if (status === "cancelled") return "cancelled" as const;
  if (status === "cancel_requested") return "cancel_requested" as const;
  if (status === "paused") return "paused" as const;
  if (status === "partially_completed") return "partially_completed" as const;
  return "review_required" as const;
}

export function FinalVideoStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const demo = projectId === demoProjectId || !project;
  const videoTitle = demo ? demoVideoTitle : getApprovedVideoTitle(runtime, projectId, lessonId);
  const approvedFine = getApprovedFineStoryboard(runtime, projectId, lessonId);
  const adoptedShotCount = approvedFine?.adoptedShots?.length ?? 0;
  const approvedStyle = getApprovedVideoStyle(runtime, projectId, lessonId)?.selectedId;
  const previewVariant = approvedStyle === "clay" ? 1 : approvedStyle === "clean" ? 2 : 0;
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:final-video`];
  const stale = nodeState?.status === "stale";
  const approved = nodeState?.status === "approved";
  const nodeRunId = nodeState?.id;
  const taskDraftKey = `project:${projectId}:lesson:${lessonId}:final-video-task`;
  const taskReference = runtime.drafts[taskDraftKey]?.value as { taskId?: unknown } | undefined;
  const referencedTaskId =
    typeof taskReference?.taskId === "string" ? taskReference.taskId : undefined;
  const taskBelongsToNode = (task: (typeof runtime.tasks)[number]) =>
    task.project_id === projectId && task.node_run_id === nodeRunId;
  const referencedTaskCandidate = referencedTaskId
    ? runtime.tasks.find((task) => task.id === referencedTaskId)
    : undefined;
  const referencedTask =
    referencedTaskCandidate && taskBelongsToNode(referencedTaskCandidate)
      ? referencedTaskCandidate
      : undefined;
  const nodeTask = nodeRunId ? runtime.tasks.find((task) => taskBelongsToNode(task)) : undefined;
  const resolvedTask = referencedTask ?? nodeTask;
  const invalidTaskReference = Boolean(referencedTaskId && !referencedTask && !nodeTask);
  const activeTask =
    resolvedTask && (resolvedTask.status === "queued" || resolvedTask.status === "running")
      ? resolvedTask
      : undefined;
  const rendering = activeTask !== undefined;
  const syncingTaskStatus = ["queued", "running", "cancel_requested", "paused"].includes(
    nodeState?.status ?? "",
  );
  const displayStatus = invalidTaskReference
    ? "failed"
    : syncingTaskStatus && resolvedTask && !rendering
      ? settledTaskStatus(resolvedTask.status)
      : (nodeState?.status ?? "review_required");
  const synthesisNeedsAction = [
    "failed",
    "cancelled",
    "paused",
    "partially_completed",
    "stale",
  ].includes(displayStatus);
  const cancellationPending = displayStatus === "cancel_requested";
  const waitingForTask = nodeState?.status === "running" && !activeTask && !invalidTaskReference;
  const synthesisLock = useRef(false);
  const [message, setMessage] = useState("");
  const { openContextDrawer } = useWorkbenchUi();
  useEffect(() => {
    if (!rendering) synthesisLock.current = false;
  }, [rendering]);

  useEffect(() => {
    if (!resolvedTask || rendering || !syncingTaskStatus) return;
    const nextStatus = settledTaskStatus(resolvedTask.status);
    if (nodeState?.status === nextStatus) return;
    updateMockNodeState(projectId, lessonId, "final-video", {
      status: nextStatus,
      title: "合成完整视频",
    });
    if (nextStatus === "review_required") {
      setMessage("成片已经合成完成，请检查后确认。");
    }
  }, [
    lessonId,
    nodeState?.status,
    projectId,
    resolvedTask,
    resolvedTask?.status,
    rendering,
    syncingTaskStatus,
  ]);

  const startSynthesis = () => {
    if (rendering || synthesisLock.current) return;
    synthesisLock.current = true;
    const runningNode = updateMockNodeState(projectId, lessonId, "final-video", {
      stale_reason: null,
      status: "running",
      title: "合成完整视频",
    });
    const task = createMockTask({
      detail: "正在重新合成旁白、字幕和已采用片段",
      node_run_id: runningNode.id,
      progress: 18,
      project_id: projectId,
      stage: "合成声音与字幕",
      status: "running",
      title: "课堂导入视频重新合成",
    });
    saveMockDraft(
      taskDraftKey,
      { taskId: task.id },
      { lessonId, nodeKey: "final-video", projectId },
    );
    setMessage("重新合成已开始，可在处理进度中查看。");
  };
  return (
    <WorkbenchPageFrame>
      <FocusPageHeader
        action={
          approved ? (
            <Button
              disabled={rendering}
              onClick={() =>
                updateMockNodeState(projectId, lessonId, "final-video", {
                  status: "review_required",
                  title: "合成完整视频",
                })
              }
              size="md"
              variant="secondary"
            >
              <PencilLine aria-hidden="true" />
              重新检查
            </Button>
          ) : cancellationPending ? (
            <Button disabled size="md">
              <LoaderCircle aria-hidden="true" className="animate-spin" />
              正在取消合成
            </Button>
          ) : synthesisNeedsAction ? (
            <Button disabled={rendering} onClick={startSynthesis} size="md">
              <RotateCcw aria-hidden="true" />
              {displayStatus === "paused" ? "继续合成" : "重新合成"}
            </Button>
          ) : (
            <Button
              disabled={rendering || waitingForTask}
              onClick={() =>
                updateMockNodeState(projectId, lessonId, "final-video", {
                  stale_reason: null,
                  status: "approved",
                  title: "合成完整视频",
                })
              }
              size="md"
            >
              {rendering ? (
                <LoaderCircle aria-hidden="true" className="animate-spin" />
              ) : (
                <Check aria-hidden="true" />
              )}
              {rendering ? "成片合成中" : waitingForTask ? "正在同步成片" : "确认成片"}
            </Button>
          )
        }
        eyebrow="当前要做：检查课堂导入视频成片"
        hideEyebrow
        status={<StatusBadge status={rendering ? "running" : displayStatus} />}
        title={`${videoTitle} · ${adoptedShotCount > 0 ? `${String(adoptedShotCount)} 个片段` : "完整视频"}`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="flex items-center justify-center rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-player)] p-3 md:p-4 lg:max-h-[calc(100dvh-270px)]">
          <div
            className="w-full max-w-[min(960px,max(280px,calc((100dvh-302px)*1.7778)))]"
            data-testid="final-video-preview"
          >
            <VideoScenePreview topic={demo ? undefined : videoTitle} variant={previewVariant} />
          </div>
        </section>
        <aside className="grid content-start gap-2 sm:grid-cols-2 lg:grid-cols-1">
          {[
            [FileCheck2, "技术检查", "画幅、编码、音量通过"],
            [Volume2, "旁白", "3 段 · 数学读法通过"],
            [Music, "音乐与音效", "音量平衡通过"],
            [Subtitles, "字幕", "可读时长与断句通过"],
          ].map(([Icon, title, detail]) => {
            const Comp = Icon as typeof FileCheck2;
            return (
              <div
                className="flex items-start gap-3 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3"
                key={String(title)}
              >
                <Comp
                  aria-hidden="true"
                  className="mt-0.5 size-4 shrink-0 text-[var(--sh-success)]"
                />
                <div>
                  <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">
                    {String(title)}
                  </p>
                  <p className="mt-0.5 text-xs text-[var(--sh-ink-muted)]">{String(detail)}</p>
                </div>
              </div>
            );
          })}
        </aside>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          onClick={() =>
            downloadExampleFile(
              `${videoTitle}_预览说明.txt`,
              `${videoTitle}课堂导入视频预览\n时长：00:55\n画幅：16:9\n包含旁白、音乐与字幕检查结果。`,
            )
          }
          size="sm"
          variant="secondary"
        >
          <Download aria-hidden="true" />
          下载预览说明
        </Button>
        <Button onClick={() => openContextDrawer("checks")} size="sm" variant="quiet">
          查看质量报告
        </Button>
        <Button
          disabled={rendering || cancellationPending}
          onClick={startSynthesis}
          size="sm"
          variant="quiet"
        >
          {cancellationPending ? "正在取消" : rendering ? "正在合成" : "重新合成"}
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
