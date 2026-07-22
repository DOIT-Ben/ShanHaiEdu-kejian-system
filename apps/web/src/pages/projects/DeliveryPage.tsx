import {
  CheckCircle2,
  Download,
  FileArchive,
  FileText,
  type LucideIcon,
  Presentation,
  Subtitles,
  Video,
} from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import type { WorkflowStatus } from "@/entities/workflow/model";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import {
  getConfirmedFinalVideoMedia,
  type PlayableVideoMedia,
  type SubtitleFormat,
} from "@/features/workbench/lib/videoMedia";
import { saveMockDraft, type MockRuntimeState, useMockRuntime } from "@/shared/api/mockClient";
import { listMockSavedResults } from "@/shared/api/mocks/savedResults";
import { downloadExampleFile } from "@/shared/lib/downloadExampleFile";
import { downloadRemoteFile } from "@/shared/lib/downloadRemoteFile";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";

type DeliveryRequirementKind = "lesson-plan" | "ppt" | "video";

export type DeliveryRequirement = {
  key: string;
  kind: DeliveryRequirementKind;
  label: string;
  lessonTitle: string;
  media?: PlayableVideoMedia;
  revision: number;
  status: WorkflowStatus;
};

type DeliveryFile = {
  acceptedMimeTypes?: readonly string[];
  detail: string;
  downloadUrl?: string;
  icon: LucideIcon;
  name: string;
  placeholder?: boolean;
  status: WorkflowStatus;
};

const disabledBranchStatuses = new Set<WorkflowStatus>(["disabled", "skipped"]);

function subtitleDownloadDetails(format: SubtitleFormat) {
  return format === "vtt"
    ? { acceptedMimeTypes: ["text/vtt"], extension: "vtt" }
    : {
        acceptedMimeTypes: ["application/x-subrip", "application/srt", "text/srt", "text/plain"],
        extension: "srt",
      };
}

function nodeStatus(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  nodeKey: string,
  fallback: WorkflowStatus,
) {
  const node = runtime.nodeStates[`${projectId}:${lessonId}:${nodeKey}`];
  return { revision: node?.revision ?? 0, status: node?.status ?? fallback };
}

export function buildDeliveryRequirements(runtime: MockRuntimeState, projectId: string) {
  const lessonItems = getApprovedProjectLessons(runtime, projectId);
  if (lessonItems.length === 0) {
    return [
      {
        key: `${projectId}:lesson-division`,
        kind: "lesson-plan" as const,
        label: "课时安排",
        lessonTitle: "尚未安排课时",
        revision: runtime.nodeStates[`${projectId}:*:lesson-division`]?.revision ?? 0,
        status: "not_ready" as const,
      },
    ];
  }

  return lessonItems.flatMap<DeliveryRequirement>((lesson, index) => {
    const lessonLabel = `第 ${String(index + 1)} 课时`;
    const plan = nodeStatus(runtime, projectId, lesson.id, "lesson-plan", lesson.planStatus);
    const requirements: DeliveryRequirement[] = [
      {
        key: `${lesson.id}:lesson-plan`,
        kind: "lesson-plan",
        label: `${lessonLabel} · 教案`,
        lessonTitle: lesson.title,
        ...plan,
      },
    ];
    if (!disabledBranchStatuses.has(lesson.pptStatus)) {
      requirements.push({
        key: `${lesson.id}:ppt-pages`,
        kind: "ppt",
        label: `${lessonLabel} · PPT`,
        lessonTitle: lesson.title,
        ...nodeStatus(runtime, projectId, lesson.id, "ppt-pages", lesson.pptStatus),
      });
    }
    if (!disabledBranchStatuses.has(lesson.videoStatus)) {
      const finalVideo = nodeStatus(
        runtime,
        projectId,
        lesson.id,
        "final-video",
        lesson.videoStatus,
      );
      const media = getConfirmedFinalVideoMedia(runtime, projectId, lesson.id);
      requirements.push({
        key: `${lesson.id}:final-video`,
        kind: "video",
        label: `${lessonLabel} · 课堂导入视频`,
        lessonTitle: lesson.title,
        revision: finalVideo.revision,
        status: media ? finalVideo.status : "not_ready",
        ...(media ? { media } : {}),
      });
    }
    return requirements;
  });
}

export function createDeliveryFingerprint(runtime: MockRuntimeState, projectId: string) {
  const requirements = buildDeliveryRequirements(runtime, projectId);
  const savedResults = listMockSavedResults(runtime, projectId)
    .map(({ resultId, savedAt, slotKey, version }) => ({ resultId, savedAt, slotKey, version }))
    .sort((left, right) => left.slotKey.localeCompare(right.slotKey));
  return JSON.stringify({
    lessonRevision: runtime.nodeStates[`${projectId}:*:lesson-division`]?.revision ?? 0,
    requirements: requirements.map(({ key, media, revision, status }) => ({
      key,
      media: media
        ? {
            mimeType: media.mimeType,
            src: media.src,
            subtitleFormat: media.subtitleFormat ?? null,
            subtitleSrc: media.subtitleSrc ?? null,
          }
        : null,
      revision,
      status,
    })),
    savedResults,
  });
}

function aggregateStatus(requirements: DeliveryRequirement[], kind: DeliveryRequirementKind) {
  const matching = requirements.filter((requirement) => requirement.kind === kind);
  if (matching.length === 0) return null;
  return matching.find((requirement) => requirement.status !== "approved")?.status ?? "approved";
}

function deliveryFiles(
  projectTitle: string,
  requirements: DeliveryRequirement[],
  packageApproved: boolean,
) {
  const files = requirements.flatMap<DeliveryFile>((requirement) => {
    const prefix = `${projectTitle}_${requirement.lessonTitle}`;
    if (requirement.kind === "lesson-plan") {
      return [
        {
          name: `${prefix}_教案.docx`,
          detail: `${requirement.label} · 当前版本说明`,
          icon: FileText,
          status: requirement.status,
        },
        {
          name: `${prefix}_教案.pdf`,
          detail: `${requirement.label} · 当前版本说明`,
          icon: FileText,
          status: requirement.status,
        },
      ];
    }
    if (requirement.kind === "ppt") {
      return [
        {
          name: `${prefix}_课堂课件.pptx`,
          detail: `${requirement.label} · 当前版本说明`,
          icon: Presentation,
          status: requirement.status,
        },
      ];
    }
    if (!requirement.media) {
      return [
        {
          name: `${prefix}_视频尚未生成`,
          detail: `${requirement.label} · 当前只有关键帧参考，收到真实视频后才会提供下载`,
          icon: Video,
          placeholder: true,
          status: "not_ready",
        },
      ];
    }
    const extension = requirement.media.mimeType.toLowerCase().includes("webm") ? "webm" : "mp4";
    const videoFile: DeliveryFile = {
      acceptedMimeTypes: ["video/*"],
      name: `${prefix}_课堂导入.${extension}`,
      detail: `${requirement.label} · 可播放视频文件`,
      downloadUrl: requirement.media.src,
      icon: Video,
      status: requirement.status,
    };
    if (!requirement.media.subtitleSrc || !requirement.media.subtitleFormat) return [videoFile];
    const subtitle = subtitleDownloadDetails(requirement.media.subtitleFormat);
    return [
      videoFile,
      {
        acceptedMimeTypes: subtitle.acceptedMimeTypes,
        name: `${prefix}_课堂导入字幕.${subtitle.extension}`,
        detail: `${requirement.label} · 独立字幕文件`,
        downloadUrl: requirement.media.subtitleSrc,
        icon: Subtitles,
        status: requirement.status,
      },
    ];
  });
  files.push({
    name: `${projectTitle}_质量报告.pdf`,
    detail: "教学内容与当前可用媒体检查 · 当前说明",
    icon: CheckCircle2,
    status: packageApproved ? "approved" : "not_ready",
  });
  return files;
}

function packageStatus(value: unknown) {
  if (value === "ready") return { fingerprint: null, status: "ready" };
  if (!value || typeof value !== "object" || !("status" in value)) return null;
  const candidate = value as { fingerprint?: unknown; status?: unknown };
  if (candidate.status !== "ready" && candidate.status !== "stale") return null;
  return {
    fingerprint: typeof candidate.fingerprint === "string" ? candidate.fingerprint : null,
    status: candidate.status,
  };
}

export function DeliveryPage() {
  const { projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const requirements = buildDeliveryRequirements(runtime, projectId);
  const allApproved = requirements.every((requirement) => requirement.status === "approved");
  const currentFingerprint = createDeliveryFingerprint(runtime, projectId);
  const packageKey = `project:${projectId}:delivery-package`;
  const storedPackage = packageStatus(runtime.drafts[packageKey]?.value);
  const packageReady =
    allApproved &&
    storedPackage?.status === "ready" &&
    storedPackage.fingerprint === currentFingerprint;
  const packageStale = storedPackage !== null && !packageReady;
  const [preparing, setPreparing] = useState(false);
  const [downloadingFile, setDownloadingFile] = useState<string | null>(null);
  const [downloadFeedback, setDownloadFeedback] = useState<{
    fileName: string;
    status: "error" | "success";
  } | null>(null);
  const stage = preparing ? "preparing" : packageReady ? "ready" : "idle";
  const files = deliveryFiles(project?.title ?? "课堂作品", requirements, allApproved);
  const preparePackage = () => {
    if (stage === "ready") {
      downloadExampleFile(
        `${project?.title ?? "课堂作品"}_完整交付清单.txt`,
        `山海教育课堂作品交付包\n${files.map((file) => file.name).join("\n")}`,
      );
      return;
    }
    if (!allApproved) return;
    setPreparing(true);
    window.setTimeout(() => {
      saveMockDraft(
        packageKey,
        {
          fingerprint: currentFingerprint,
          preparedAt: new Date().toISOString(),
          requirements: requirements.map(({ key, label, revision, status }) => ({
            key,
            label,
            revision,
            status,
          })),
          status: "ready",
        },
        { projectId },
      );
      setPreparing(false);
    }, 450);
  };
  const downloadDeliveryFile = async (file: DeliveryFile) => {
    if (!file.downloadUrl || !file.acceptedMimeTypes || downloadingFile) return;
    setDownloadingFile(file.name);
    setDownloadFeedback(null);
    try {
      await downloadRemoteFile({
        acceptedMimeTypes: file.acceptedMimeTypes,
        filename: file.name,
        url: file.downloadUrl,
      });
      setDownloadFeedback({ fileName: file.name, status: "success" });
    } catch {
      setDownloadFeedback({ fileName: file.name, status: "error" });
    } finally {
      setDownloadingFile(null);
    }
  };
  const lessonPlanStatus = aggregateStatus(requirements, "lesson-plan") ?? "not_ready";
  const pptStatus = aggregateStatus(requirements, "ppt");
  const videoStatus = aggregateStatus(requirements, "video");
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-4 md:px-6">
      <FocusPageHeader
        action={
          <Button
            disabled={stage === "preparing" || !allApproved}
            onClick={preparePackage}
            size="md"
          >
            <FileArchive aria-hidden="true" />
            {stage === "preparing"
              ? "正在准备交付包"
              : stage === "ready"
                ? "下载交付清单"
                : allApproved
                  ? "准备完整交付包"
                  : "等待全部批准"}
          </Button>
        }
        description="交付只包含已启用内容的当前确认版本，不包含未采用的备选作品和未完成内容。"
        title="项目交付"
      />
      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_minmax(260px,0.6fr)]">
        <section className="rounded-[var(--sh-radius-sm)] border border-[var(--sh-warning)]/30 bg-[var(--sh-warning-soft)] p-4 text-sm text-[var(--sh-ink-default)]">
          <p className="font-semibold">交付门槛</p>
          <ul className="mt-2 grid gap-x-5 gap-y-1 sm:grid-cols-2">
            {requirements.map((requirement) => (
              <li className="flex items-center justify-between gap-3" key={requirement.key}>
                <span>{requirement.label}</span>
                <StatusBadge status={requirement.status} />
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-[var(--sh-ink-muted)]">
            已启用内容的当前版本全部批准后，才能准备交付包。
          </p>
        </section>
        <section className="grid gap-3 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4 sm:grid-cols-3 lg:grid-cols-1">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-[var(--sh-ink-muted)]">教案总体状态</p>
            <StatusBadge status={lessonPlanStatus} />
          </div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-[var(--sh-ink-muted)]">PPT 总体状态</p>
            <StatusBadge status={pptStatus ?? "disabled"} />
          </div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-[var(--sh-ink-muted)]">视频总体状态</p>
            <StatusBadge status={videoStatus ?? "disabled"} />
          </div>
        </section>
      </div>
      {packageStale ? (
        <p className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm font-semibold text-[var(--sh-ink-default)]">
          批准状态或当前成果已变化，原交付包已失效；请完成审批后重新准备。
        </p>
      ) : null}
      {stage === "ready" ? (
        <p className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-success-soft)] p-3 text-sm font-semibold text-[var(--sh-success)]">
          交付包已准备完成，可以下载。
        </p>
      ) : null}
      {downloadFeedback ? (
        <p
          className={`mt-3 rounded-[var(--sh-radius-sm)] p-3 text-sm font-semibold ${
            downloadFeedback.status === "success"
              ? "bg-[var(--sh-success-soft)] text-[var(--sh-success)]"
              : "bg-[var(--sh-danger-soft)] text-[var(--sh-danger)]"
          }`}
          role={downloadFeedback.status === "error" ? "alert" : "status"}
        >
          {downloadFeedback.status === "success"
            ? `“${downloadFeedback.fileName}”已开始下载。`
            : `“${downloadFeedback.fileName}”暂时无法下载。请稍后重试；若仍失败，请联系管理员检查文件访问权限。`}
        </p>
      ) : null}
      <div className="mt-4 divide-y divide-[var(--sh-line-subtle)] rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-4">
        {files.map((file) => {
          const { detail, downloadUrl, icon: Icon, name, placeholder, status } = file;
          const isDownloading = downloadingFile === name;
          const downloadFailed =
            downloadFeedback?.fileName === name && downloadFeedback.status === "error";
          return (
            <div className="flex flex-wrap items-center gap-3 py-3.5" key={name}>
              <span className="grid size-9 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-600)]">
                <Icon aria-hidden="true" className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-[var(--sh-ink-strong)]">{name}</p>
                <p className="mt-1 text-xs text-[var(--sh-ink-muted)]">{detail}</p>
              </div>
              <StatusBadge status={status} />
              {downloadUrl && packageReady && status === "approved" ? (
                <Button
                  disabled={downloadingFile !== null}
                  onClick={() => void downloadDeliveryFile(file)}
                  size="sm"
                  variant="secondary"
                >
                  <Download aria-hidden="true" />
                  {isDownloading ? "正在下载" : downloadFailed ? "重新下载" : "下载文件"}
                </Button>
              ) : (
                <Button
                  disabled={placeholder || !packageReady || status !== "approved"}
                  onClick={() =>
                    downloadExampleFile(
                      `${name}.说明.txt`,
                      `山海教育课堂作品：${name}\n${detail}\n当前提供文件说明，正式文件将在导出完成后提供。`,
                    )
                  }
                  size="sm"
                  variant="secondary"
                >
                  <Download aria-hidden="true" />
                  {placeholder ? "视频尚未生成" : packageReady ? "下载文件说明" : "等待交付包"}
                </Button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
