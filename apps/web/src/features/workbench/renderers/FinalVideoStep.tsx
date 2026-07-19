import {
  Check,
  Clock3,
  Download,
  FileCheck2,
  LoaderCircle,
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
import { getPlayableFinalVideo } from "@/features/workbench/lib/videoMedia";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import {
  createMockTask,
  saveMockDraft,
  updateMockNodeState,
  useMockRuntime,
} from "@/shared/api/mocks/runtime";
import { downloadExampleFile } from "@/shared/lib/downloadExampleFile";
import { downloadRemoteFile } from "@/shared/lib/downloadRemoteFile";
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
  const playableVideo = getPlayableFinalVideo(runtime, projectId, lessonId);
  const hasPlayableVideo = playableVideo !== null;
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
  const truthfulDisplayStatus =
    hasPlayableVideo || rendering || waitingForTask || cancellationPending || synthesisNeedsAction
      ? displayStatus
      : "not_ready";
  const synthesisLock = useRef(false);
  const [message, setMessage] = useState("");
  const [videoDownloadState, setVideoDownloadState] = useState<"error" | "idle" | "loading">(
    "idle",
  );
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
      title: "生成课堂导入视频",
    });
    if (nextStatus === "review_required") {
      setMessage(
        hasPlayableVideo
          ? "画面文件已准备好，请完整播放后再确认。声音与字幕按当前可用能力分别检查。"
          : "生成任务已结束，但尚未收到可播放的视频文件。当前只显示关键帧示意。",
      );
    }
  }, [
    lessonId,
    nodeState?.status,
    projectId,
    resolvedTask,
    resolvedTask?.status,
    rendering,
    syncingTaskStatus,
    hasPlayableVideo,
  ]);

  const startSynthesis = () => {
    if (rendering || synthesisLock.current) return;
    synthesisLock.current = true;
    const runningNode = updateMockNodeState(projectId, lessonId, "final-video", {
      stale_reason: null,
      status: "running",
      title: "生成课堂导入视频",
    });
    const task = createMockTask({
      detail: "正在生成画面、旁白和字幕",
      node_run_id: runningNode.id,
      progress: 18,
      project_id: projectId,
      stage: "生成声音与字幕",
      status: "running",
      title: "课堂导入视频生成",
    });
    saveMockDraft(
      taskDraftKey,
      { taskId: task.id },
      { lessonId, nodeKey: "final-video", projectId },
    );
    setMessage("视频生成已开始，可在处理进度中查看。");
  };
  const downloadVideo = async () => {
    if (!playableVideo || videoDownloadState === "loading") return;
    setVideoDownloadState("loading");
    try {
      const extension = playableVideo.mimeType.toLowerCase().includes("webm") ? "webm" : "mp4";
      await downloadRemoteFile({
        acceptedMimeTypes: ["video/*"],
        filename: `${videoTitle}_课堂导入.${extension}`,
        url: playableVideo.src,
      });
      setVideoDownloadState("idle");
      setMessage("视频文件已开始下载。");
    } catch {
      setVideoDownloadState("error");
    }
  };
  const reviewItems = hasPlayableVideo
    ? [
        [FileCheck2, "画面待确认", "完整播放一遍，确认画面清楚、没有卡顿"],
        [Volume2, "声音待确认", "当前文件可能不含旁白；完整配音属于后续能力"],
        playableVideo.subtitleSrc
          ? [Subtitles, "字幕待确认", "已提供独立字幕文件，请检查停留时间和断句"]
          : [Subtitles, "字幕文件未提供", "当前阶段不以真实字幕阻塞画面文件确认"],
      ]
    : [
        [FileCheck2, "画面尚未检查", "视频生成后，再确认画面是否正常"],
        [Volume2, "声音尚未检查", "视频生成后，再确认声音是否清楚"],
        [Subtitles, "字幕尚未检查", "视频生成后，再确认字幕是否易读"],
      ];
  return (
    <WorkbenchPageFrame>
      <FocusPageHeader
        action={
          approved && hasPlayableVideo ? (
            <Button
              disabled={rendering}
              onClick={() =>
                updateMockNodeState(projectId, lessonId, "final-video", {
                  status: "review_required",
                  title: "生成课堂导入视频",
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
              正在取消生成
            </Button>
          ) : synthesisNeedsAction ? (
            <Button disabled={rendering} onClick={startSynthesis} size="md">
              <RotateCcw aria-hidden="true" />
              {displayStatus === "paused" ? "继续生成视频" : "重新生成视频"}
            </Button>
          ) : rendering || waitingForTask ? (
            <Button disabled size="md">
              <LoaderCircle aria-hidden="true" className="animate-spin" />
              {rendering ? "视频生成中" : "正在同步视频"}
            </Button>
          ) : hasPlayableVideo ? (
            <Button
              onClick={() =>
                updateMockNodeState(projectId, lessonId, "final-video", {
                  stale_reason: null,
                  status: "approved",
                  title: "生成课堂导入视频",
                })
              }
              size="md"
            >
              <Check aria-hidden="true" />
              确认画面文件
            </Button>
          ) : (
            <Button disabled size="md" variant="secondary">
              <Clock3 aria-hidden="true" />
              视频尚未生成
            </Button>
          )
        }
        description={
          hasPlayableVideo
            ? "完整播放一遍，先确认画面文件；声音与字幕按当前可用能力分别检查。"
            : "当前只有关键帧示意。收到可播放的视频文件后，才会开放播放与确认。"
        }
        eyebrow="当前要做：查看课堂导入视频生成状态"
        hideEyebrow
        status={<StatusBadge status={rendering ? "running" : truthfulDisplayStatus} />}
        title={`${videoTitle} · ${hasPlayableVideo ? "可播放画面文件" : adoptedShotCount > 0 ? `${String(adoptedShotCount)} 个关键帧参考` : "关键帧示意"}`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="flex items-center justify-center rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-player)] p-3 md:p-4 lg:max-h-[calc(100dvh-270px)]">
          <div
            className="w-full max-w-[min(960px,max(280px,calc((100dvh-302px)*1.7778)))]"
            data-testid="final-video-preview"
          >
            {playableVideo ? (
              <video
                aria-label={`${videoTitle}课堂导入视频`}
                className="aspect-video size-full rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-player)] object-contain"
                controls
                preload="metadata"
              >
                <source src={playableVideo.src} type={playableVideo.mimeType} />
                {playableVideo.subtitleSrc ? (
                  <track
                    default
                    kind="subtitles"
                    label="中文字幕"
                    src={playableVideo.subtitleSrc}
                    srcLang="zh-CN"
                  />
                ) : null}
              </video>
            ) : (
              <VideoScenePreview
                topic={demo ? undefined : videoTitle}
                variant={demo ? 3 : previewVariant}
              />
            )}
          </div>
        </section>
        <aside className="grid content-start gap-2 sm:grid-cols-2 lg:grid-cols-1">
          {reviewItems.map(([Icon, title, detail]) => {
            const Comp = Icon as typeof FileCheck2;
            return (
              <div
                className="flex items-start gap-3 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3"
                key={String(title)}
              >
                <Comp
                  aria-hidden="true"
                  className="mt-0.5 size-4 shrink-0 text-[var(--sh-brand-600)]"
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
        {playableVideo ? (
          <Button
            disabled={videoDownloadState === "loading"}
            onClick={() => void downloadVideo()}
            size="sm"
            variant="secondary"
          >
            {videoDownloadState === "loading" ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" />
            ) : (
              <Download aria-hidden="true" />
            )}
            {videoDownloadState === "loading"
              ? "正在下载视频"
              : videoDownloadState === "error"
                ? "重新下载视频"
                : "下载视频"}
          </Button>
        ) : (
          <Button
            onClick={() =>
              downloadExampleFile(
                `${videoTitle}_关键帧说明.txt`,
                `${videoTitle}关键帧示意\n当前仅有关键帧参考，视频尚未生成。\n收到可播放的视频文件后，才会开放播放、检查与确认。`,
              )
            }
            size="sm"
            variant="secondary"
          >
            <Download aria-hidden="true" />
            下载关键帧说明
          </Button>
        )}
        {hasPlayableVideo ? (
          <Button onClick={() => openContextDrawer("checks")} size="sm" variant="quiet">
            查看检查项
          </Button>
        ) : null}
        <Button
          disabled={rendering || cancellationPending}
          onClick={startSynthesis}
          size="sm"
          variant="quiet"
        >
          {cancellationPending
            ? "正在取消"
            : rendering
              ? "正在生成"
              : resolvedTask
                ? "重新生成视频"
                : "开始生成视频"}
        </Button>
      </div>
      {videoDownloadState === "error" ? (
        <p className="mt-3 text-sm font-medium text-[var(--sh-danger)]" role="alert">
          视频文件暂时无法下载。请稍后重试；若仍失败，请联系管理员检查文件访问权限。
        </p>
      ) : null}
      {message ? (
        <p
          className={`mt-3 text-sm font-medium ${hasPlayableVideo ? "text-[var(--sh-success)]" : "text-[var(--sh-warning)]"}`}
          role="status"
        >
          {message}
        </p>
      ) : null}
    </WorkbenchPageFrame>
  );
}
