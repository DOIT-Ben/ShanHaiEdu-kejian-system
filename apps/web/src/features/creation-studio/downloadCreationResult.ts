import { presentationPreviewPages, type StudioType } from "@/features/creation-studio/model";
import { downloadExampleFile } from "@/shared/lib/downloadExampleFile";

export type CreationDownloadResult =
  { status: "started" } | { message: string; status: "unavailable" };

const IMAGE_DOWNLOAD_UNAVAILABLE = "当前作品图片暂时无法直接下载，请保存到项目后从成果页下载。";

function currentRenderedImageSource() {
  if (typeof document === "undefined") return undefined;
  const image = document.querySelector<HTMLImageElement>(
    '[data-testid="creation-main-visual"] img[data-creation-asset-source]',
  );
  return (
    image?.currentSrc ||
    image?.dataset.creationAssetSource ||
    image?.getAttribute("src") ||
    undefined
  );
}

function downloadableImageUrl(source: string) {
  const value = source.trim();
  if (/^blob:/i.test(value) || /^data:image\//i.test(value)) return value;
  if (typeof document === "undefined" || typeof window === "undefined") return undefined;
  try {
    const url = new URL(value, document.baseURI);
    if (
      (url.protocol === "http:" || url.protocol === "https:") &&
      url.origin === window.location.origin
    ) {
      return url.href;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

function extensionFor(source: string | Blob) {
  if (source instanceof Blob) {
    if (source.type === "image/png") return "png";
    if (source.type === "image/jpeg") return "jpg";
    if (source.type === "image/svg+xml") return "svg";
    return "webp";
  }
  const dataType = /^data:image\/(png|jpeg|webp|gif|svg\+xml)/i.exec(source)?.[1]?.toLowerCase();
  if (dataType) return dataType === "jpeg" ? "jpg" : dataType === "svg+xml" ? "svg" : dataType;
  try {
    const extension = /\.(png|jpe?g|webp|gif|svg)$/i.exec(
      new URL(source, document.baseURI).pathname,
    )?.[1];
    if (extension) return extension.toLowerCase() === "jpeg" ? "jpg" : extension.toLowerCase();
  } catch {
    // The source is validated separately; an unknown extension falls back to WebP for bundled assets.
  }
  return "webp";
}

function startImageDownload(source: string | Blob, filename: string) {
  let objectUrl: string | undefined;
  let href: string;
  if (typeof source === "string") {
    href = source;
  } else {
    objectUrl = URL.createObjectURL(source);
    href = objectUrl;
  }
  const anchor = document.createElement("a");
  anchor.download = filename;
  anchor.href = href;
  anchor.hidden = true;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  if (objectUrl) window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
}

function unavailableImageDownload(): CreationDownloadResult {
  if (typeof window !== "undefined" && typeof window.alert === "function") {
    window.alert(IMAGE_DOWNLOAD_UNAVAILABLE);
  }
  return { message: IMAGE_DOWNLOAD_UNAVAILABLE, status: "unavailable" };
}

export function downloadCreationResult({
  imageSource,
  candidate,
  ratio,
  title,
  type,
}: {
  imageSource?: Blob | string;
  candidate: number;
  ratio: string;
  title: string;
  type: StudioType;
}): CreationDownloadResult {
  const candidateLabel = String(candidate + 1);
  if (type === "image") {
    const source = imageSource ?? currentRenderedImageSource();
    if (!source || typeof document === "undefined") return unavailableImageDownload();
    if (source instanceof Blob) {
      if (!source.type.startsWith("image/")) return unavailableImageDownload();
      startImageDownload(source, `${title}_作品${candidateLabel}.${extensionFor(source)}`);
      return { status: "started" };
    }
    const url = downloadableImageUrl(source);
    if (!url) return unavailableImageDownload();
    startImageDownload(url, `${title}_作品${candidateLabel}.${extensionFor(url)}`);
    return { status: "started" };
  }
  if (type === "video") {
    downloadExampleFile(
      `${title}_关键帧${candidateLabel}_说明.txt`,
      `${title}关键帧说明\n关键帧：${candidateLabel}\n画面比例：${ratio}\n当前仅为关键帧示意，视频尚未生成。\n收到真实视频文件后，才会开放播放、确认和视频下载。`,
    );
    return { status: "started" };
  }
  const pages = presentationPreviewPages
    .map(
      (pageTitle, index) =>
        `<section><span>第 ${String(index + 1)} 页</span><h2>${pageTitle}</h2><p>${index === 0 ? "从真实课堂情境进入百分数。" : "每页只承担一个教学任务，并保留清晰图示。"}</p></section>`,
    )
    .join("");
  downloadExampleFile(
    `${title}_作品${candidateLabel}_页面预览.html`,
    `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>${title}页面预览</title><style>body{font-family:Inter,"PingFang SC","Microsoft YaHei",sans-serif;margin:48px;color:#5C5248;background:#FFF9F2}section{box-sizing:border-box;aspect-ratio:16/9;max-width:960px;border:1px solid #E8DCCE;border-radius:16px;margin:24px auto;padding:7%;background:#fff;box-shadow:0 2px 8px rgba(166,139,110,.08)}span{font-size:14px;color:#8B7355}h1,h2{color:#6B5344}h1{max-width:960px;margin:0 auto}</style><h1>${title} · 作品 ${candidateLabel}</h1>${pages}</html>`,
    "text/html;charset=utf-8",
  );
  return { status: "started" };
}
