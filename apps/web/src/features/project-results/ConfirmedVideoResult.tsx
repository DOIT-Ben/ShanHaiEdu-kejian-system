import { Download, LoaderCircle, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { PlayableVideoMedia } from "@/features/workbench/lib/videoMedia";
import { downloadRemoteFile } from "@/shared/lib/downloadRemoteFile";
import { Button } from "@/shared/ui/Button";

type ConfirmedVideoResultProps = {
  lessonId: string;
  media: PlayableVideoMedia;
  onDownloaded: () => void;
  projectId: string;
  title: string;
};

export function ConfirmedVideoResult({
  lessonId,
  media,
  onDownloaded,
  projectId,
  title,
}: ConfirmedVideoResultProps) {
  const [downloadState, setDownloadState] = useState<"error" | "idle" | "loading">("idle");
  const downloadVideo = async () => {
    if (downloadState === "loading") return;
    setDownloadState("loading");
    try {
      const extension = media.mimeType.toLowerCase().includes("webm") ? "webm" : "mp4";
      await downloadRemoteFile({
        acceptedMimeTypes: ["video/*"],
        filename: `${title}.${extension}`,
        url: media.src,
      });
      setDownloadState("idle");
      onDownloaded();
    } catch {
      setDownloadState("error");
    }
  };

  return (
    <>
      <video
        aria-label={`${title}可播放视频`}
        className="aspect-video w-full rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-player)] object-contain"
        controls
        preload="metadata"
      >
        <source src={media.src} type={media.mimeType} />
        {media.subtitleSrc && media.subtitleFormat === "vtt" ? (
          <track
            default
            kind="subtitles"
            label="中文字幕"
            src={media.subtitleSrc}
            srcLang="zh-CN"
          />
        ) : null}
      </video>
      <p className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-success-soft)] px-3 py-2 text-xs font-medium text-[var(--sh-success)]">
        该视频已在成片页完成确认，可以播放或下载。
      </p>
      {downloadState === "error" ? (
        <p className="mt-3 text-xs font-medium text-[var(--sh-danger)]" role="alert">
          视频文件暂时无法下载。请稍后重试，或返回成片页重新检查文件。
        </p>
      ) : null}
      <div className="mt-3 flex gap-2 lg:mt-5 lg:grid">
        <Button
          aria-label={downloadState === "error" ? "重新下载视频文件" : "下载视频文件"}
          className="min-w-0 flex-1 px-2 lg:w-full"
          disabled={downloadState === "loading"}
          onClick={() => void downloadVideo()}
          size="sm"
        >
          {downloadState === "loading" ? (
            <LoaderCircle aria-hidden="true" className="animate-spin" />
          ) : downloadState === "error" ? (
            <RotateCcw aria-hidden="true" />
          ) : (
            <Download aria-hidden="true" />
          )}
          {downloadState === "loading"
            ? "正在下载"
            : downloadState === "error"
              ? "重新下载"
              : "下载视频"}
        </Button>
        <Button asChild className="min-w-0 flex-1 px-2 lg:w-full" size="sm" variant="secondary">
          <Link to={`/app/projects/${projectId}/lessons/${lessonId}/work/final-video`}>
            重新检查视频
          </Link>
        </Button>
      </div>
    </>
  );
}
