import { presentationPreviewPages, type StudioType } from "@/features/creation-studio/model";
import { downloadExampleFile } from "@/shared/lib/downloadExampleFile";

export type CreationDownloadResult =
  { status: "started" } | { message: string; status: "unavailable" };

const IMAGE_DOWNLOAD_UNAVAILABLE = "当前作品图片暂时无法直接下载，请保存到项目后从成果页下载。";

function currentRenderedImage() {
  if (typeof document === "undefined") return undefined;
  return document.querySelector<HTMLImageElement>(
    '[data-testid="creation-main-visual"] img[data-creation-asset-source]',
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

function targetDimensions(ratio: string, sourceWidth: number, sourceHeight: number) {
  if (ratio === "auto") return { height: sourceHeight, width: sourceWidth };
  if (ratio === "16:9") return { height: 900, width: 1600 };
  if (ratio === "4:3") return { height: 900, width: 1200 };
  return { height: 1024, width: 1024 };
}

function objectPositionPercent(value: string | undefined) {
  const [x = "50%", y = "50%"] = value?.trim().split(/\s+/) ?? [];
  const parse = (token: string) => {
    const parsed = Number.parseFloat(token.replace("%", ""));
    return Number.isFinite(parsed) ? Math.min(100, Math.max(0, parsed)) / 100 : 0.5;
  };
  return { x: parse(x), y: parse(y) };
}

function waitForImage(image: HTMLImageElement) {
  if (image.complete && image.naturalWidth > 0 && image.naturalHeight > 0) {
    return Promise.resolve(true);
  }
  return new Promise<boolean>((resolve) => {
    const timeout = window.setTimeout(() => finish(false), 10_000);
    const finish = (loaded: boolean) => {
      window.clearTimeout(timeout);
      image.removeEventListener("load", onLoad);
      image.removeEventListener("error", onError);
      resolve(loaded && image.naturalWidth > 0 && image.naturalHeight > 0);
    };
    const onLoad = () => finish(true);
    const onError = () => finish(false);
    image.addEventListener("load", onLoad, { once: true });
    image.addEventListener("error", onError, { once: true });
  });
}

async function loadImageSource(source: Blob | string) {
  if (typeof Image === "undefined") return undefined;
  let sourceUrl: string;
  let ownedUrl: string | undefined;
  if (source instanceof Blob) {
    ownedUrl = URL.createObjectURL(source);
    sourceUrl = ownedUrl;
  } else {
    sourceUrl = downloadableImageUrl(source) ?? "";
    if (!sourceUrl) return undefined;
  }
  const image = new Image();
  image.decoding = "async";
  image.src = sourceUrl;
  if (!(await waitForImage(image))) {
    if (ownedUrl) URL.revokeObjectURL(ownedUrl);
    return undefined;
  }
  return { image, ownedUrl };
}

async function cropImageToBlob(
  image: HTMLImageElement,
  ratio: string,
  position: { x: number; y: number },
) {
  const sourceWidth = image.naturalWidth;
  const sourceHeight = image.naturalHeight;
  if (!sourceWidth || !sourceHeight || typeof document === "undefined") return undefined;
  const { height, width } = targetDimensions(ratio, sourceWidth, sourceHeight);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) return undefined;
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";

  const sourceRatio = sourceWidth / sourceHeight;
  const targetRatio = width / height;
  let cropWidth = sourceWidth;
  let cropHeight = sourceHeight;
  let sourceX = 0;
  let sourceY = 0;
  if (sourceRatio > targetRatio) {
    cropWidth = sourceHeight * targetRatio;
    sourceX = (sourceWidth - cropWidth) * position.x;
  } else if (sourceRatio < targetRatio) {
    cropHeight = sourceWidth / targetRatio;
    sourceY = (sourceHeight - cropHeight) * position.y;
  }
  context.drawImage(image, sourceX, sourceY, cropWidth, cropHeight, 0, 0, width, height);

  return new Promise<Blob | undefined>((resolve) => {
    try {
      canvas.toBlob((blob) => resolve(blob ?? undefined), "image/webp", 0.92);
    } catch {
      resolve(undefined);
    }
  });
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

export async function downloadCreationResult({
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
}): Promise<CreationDownloadResult> {
  const candidateLabel = String(candidate + 1);
  if (type === "image") {
    if (typeof document === "undefined") return unavailableImageDownload();
    const renderedImage = currentRenderedImage();
    let image = renderedImage;
    let ownedUrl: string | undefined;
    if (imageSource !== undefined) {
      if (imageSource instanceof Blob && !imageSource.type.startsWith("image/")) {
        return unavailableImageDownload();
      }
      const loaded = await loadImageSource(imageSource);
      image = loaded?.image;
      ownedUrl = loaded?.ownedUrl;
    }
    if (!image || !(await waitForImage(image))) {
      if (ownedUrl) URL.revokeObjectURL(ownedUrl);
      return unavailableImageDownload();
    }
    const objectPosition =
      renderedImage && image === renderedImage
        ? objectPositionPercent(
            renderedImage.style.objectPosition || getComputedStyle(renderedImage).objectPosition,
          )
        : { x: 0.5, y: 0.5 };
    const cropped = await cropImageToBlob(image, ratio, objectPosition);
    if (ownedUrl) URL.revokeObjectURL(ownedUrl);
    if (!cropped) return unavailableImageDownload();
    startImageDownload(cropped, `${title}_作品${candidateLabel}.${extensionFor(cropped)}`);
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
