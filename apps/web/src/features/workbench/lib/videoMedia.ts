import {
  getMockNodeState,
  getMockRuntimeState,
  saveMockDraft,
  updateMockNodeState,
  type MockRuntimeState,
} from "@/shared/api/mocks/runtime";

export type PlayableVideoMedia = {
  mimeType: string;
  src: string;
  subtitleSrc?: string;
  subtitleFormat?: SubtitleFormat;
};

export type SubtitleFormat = "srt" | "vtt";

export type FinalVideoMediaConfirmationStatus = "confirmed" | "pending" | "unavailable";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function firstString(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return undefined;
}

function isAllowedMediaSource(value: string) {
  if (value.startsWith("/")) return true;
  try {
    const protocol = new URL(value).protocol;
    return protocol === "https:" || protocol === "http:" || protocol === "blob:";
  } catch {
    return false;
  }
}

function normalizeSubtitleFormat(value: string | undefined): SubtitleFormat | undefined {
  const normalized = value?.trim().toLowerCase();
  if (normalized === "vtt" || normalized === "webvtt") return "vtt";
  if (normalized === "srt" || normalized === "subrip") return "srt";
  return undefined;
}

function subtitleFormatFromMimeType(value: string | undefined): SubtitleFormat | undefined {
  const normalized = value?.split(";", 1)[0]?.trim().toLowerCase();
  if (normalized === "text/vtt") return "vtt";
  if (
    normalized === "application/x-subrip" ||
    normalized === "application/srt" ||
    normalized === "text/srt"
  ) {
    return "srt";
  }
  return undefined;
}

function subtitleFormatFromUrl(value: string): SubtitleFormat | undefined {
  const path = value.split(/[?#]/, 1)[0]?.toLowerCase() ?? "";
  const extension = path.slice(path.lastIndexOf(".") + 1);
  return normalizeSubtitleFormat(extension);
}

export function parsePlayableVideoMedia(value: unknown): PlayableVideoMedia | null {
  if (!isRecord(value)) return null;
  const src = firstString(value, ["src", "url", "mediaUrl", "media_url"]);
  const mimeType = firstString(value, ["mimeType", "mime_type", "contentType", "content_type"]);
  if (!src || !mimeType?.toLowerCase().startsWith("video/") || !isAllowedMediaSource(src)) {
    return null;
  }
  const subtitleCandidate = firstString(value, ["subtitleSrc", "subtitleUrl", "subtitle_url"]);
  if (!subtitleCandidate || !isAllowedMediaSource(subtitleCandidate)) {
    return { mimeType, src };
  }
  const subtitleMimeType = firstString(value, [
    "subtitleMimeType",
    "subtitleMime",
    "subtitle_content_type",
    "subtitleContentType",
  ]);
  const subtitleFormat =
    subtitleFormatFromMimeType(subtitleMimeType) ??
    normalizeSubtitleFormat(firstString(value, ["subtitleFormat", "subtitle_format"])) ??
    subtitleFormatFromUrl(subtitleCandidate);
  if (!subtitleFormat) return { mimeType, src };
  return {
    mimeType,
    src,
    subtitleFormat,
    subtitleSrc: subtitleCandidate,
  };
}

export function getPlayableFinalVideo(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
) {
  const draftKey = `project:${projectId}:lesson:${lessonId}:final-video`;
  for (const key of [`${draftKey}:media`, `${draftKey}:approved`, draftKey]) {
    const media = parsePlayableVideoMedia(runtime.drafts[key]?.value);
    if (media) return media;
  }
  return null;
}

export function finalVideoMediaConfirmationKey(projectId: string, lessonId: string) {
  return `project:${projectId}:lesson:${lessonId}:final-video:media-confirmation`;
}

export function saveFinalVideoMediaConfirmation(
  projectId: string,
  lessonId: string,
  media: PlayableVideoMedia,
  status: FinalVideoMediaConfirmationStatus,
) {
  return saveMockDraft(
    finalVideoMediaConfirmationKey(projectId, lessonId),
    {
      mimeType: media.mimeType,
      src: media.src,
      ...(media.subtitleSrc && media.subtitleFormat
        ? { subtitleFormat: media.subtitleFormat, subtitleSrc: media.subtitleSrc }
        : {}),
      status,
    },
    { lessonId, nodeKey: "final-video", projectId },
  );
}

export function invalidateFinalVideoMedia(
  projectId: string,
  lessonId: string,
  media = getPlayableFinalVideo(getMockRuntimeState(), projectId, lessonId),
) {
  if (!media) return;
  saveFinalVideoMediaConfirmation(projectId, lessonId, media, "unavailable");
  if (getMockNodeState(projectId, lessonId, "final-video")?.status === "approved") {
    updateMockNodeState(projectId, lessonId, "final-video", { status: "review_required" });
  }
}

const subtitleMimeTypes: Record<SubtitleFormat, readonly string[]> = {
  srt: ["application/x-subrip", "application/srt", "text/srt", "text/plain"],
  vtt: ["text/vtt"],
};

function normalizeMimeType(value: string | null) {
  return value?.split(";", 1)[0]?.trim().toLowerCase() ?? "";
}

function hasValidSubtitleContent(content: string, format: SubtitleFormat) {
  const normalized = content.replace(/^\uFEFF/, "").trimStart();
  if (format === "vtt") {
    return (
      /^WEBVTT(?:[ \t].*)?(?:\r?\n|$)/.test(normalized) &&
      /(?:^|\r?\n)(?:\d{2}:)?\d{2}:\d{2}\.\d{3}[ \t]+-->[ \t]+(?:\d{2}:)?\d{2}:\d{2}\.\d{3}(?:[ \t]+[^\r\n]*)?\r?\n[^\r\n]*\S/.test(
        normalized,
      )
    );
  }
  return /(?:^|\r?\n)\d+\s*\r?\n\d{2}:\d{2}:\d{2}[,.]\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}[,.]\d{3}(?:[ \t]+[^\r\n]*)?\r?\n[^\r\n]*\S/.test(
    normalized,
  );
}

export async function validateSubtitleFile(
  src: string,
  format: SubtitleFormat,
  signal?: AbortSignal,
) {
  try {
    const response = await fetch(src, {
      headers: { Accept: subtitleMimeTypes[format].join(", ") },
      signal,
    });
    if (!response.ok) return false;
    const contentType = normalizeMimeType(response.headers.get("content-type"));
    if (!contentType || !subtitleMimeTypes[format].includes(contentType)) return false;
    return hasValidSubtitleContent(await response.text(), format);
  } catch {
    return false;
  }
}

export function isFinalVideoMediaConfirmed(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  media = getPlayableFinalVideo(runtime, projectId, lessonId),
) {
  if (!media) return false;
  const value = runtime.drafts[finalVideoMediaConfirmationKey(projectId, lessonId)]?.value;
  if (!isRecord(value)) return false;
  const subtitleSrc = firstString(value, ["subtitleSrc", "subtitleUrl", "subtitle_url"]);
  const subtitleFormat = normalizeSubtitleFormat(
    firstString(value, ["subtitleFormat", "subtitle_format"]),
  );
  return (
    value.status === "confirmed" &&
    value.src === media.src &&
    value.mimeType === media.mimeType &&
    (subtitleSrc ?? null) === (media.subtitleSrc ?? null) &&
    (subtitleFormat ?? null) === (media.subtitleFormat ?? null)
  );
}

export function getConfirmedFinalVideoMedia(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
) {
  const media = getPlayableFinalVideo(runtime, projectId, lessonId);
  if (!media || runtime.nodeStates[`${projectId}:${lessonId}:final-video`]?.status !== "approved") {
    return null;
  }
  return isFinalVideoMediaConfirmed(runtime, projectId, lessonId, media) ? media : null;
}
