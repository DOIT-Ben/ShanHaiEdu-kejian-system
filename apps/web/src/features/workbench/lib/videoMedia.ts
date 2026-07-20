import type { MockRuntimeState } from "@/shared/api/mocks/runtime";

export type PlayableVideoMedia = {
  mimeType: string;
  src: string;
  subtitleSrc?: string;
};

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

export function parsePlayableVideoMedia(value: unknown): PlayableVideoMedia | null {
  if (!isRecord(value)) return null;
  const src = firstString(value, ["src", "url", "mediaUrl", "media_url"]);
  const mimeType = firstString(value, ["mimeType", "mime_type", "contentType", "content_type"]);
  if (!src || !mimeType?.toLowerCase().startsWith("video/") || !isAllowedMediaSource(src)) {
    return null;
  }
  const subtitleCandidate = firstString(value, ["subtitleSrc", "subtitleUrl", "subtitle_url"]);
  return {
    mimeType,
    src,
    ...(subtitleCandidate && isAllowedMediaSource(subtitleCandidate)
      ? { subtitleSrc: subtitleCandidate }
      : {}),
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

export function isFinalVideoMediaConfirmed(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  media = getPlayableFinalVideo(runtime, projectId, lessonId),
) {
  if (!media) return false;
  const value = runtime.drafts[finalVideoMediaConfirmationKey(projectId, lessonId)]?.value;
  if (!isRecord(value)) return false;
  return (
    value.status === "confirmed" && value.src === media.src && value.mimeType === media.mimeType
  );
}
