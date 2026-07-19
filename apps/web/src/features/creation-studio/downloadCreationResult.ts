import { presentationPreviewPages, type StudioType } from "@/features/creation-studio/model";
import { downloadExampleFile } from "@/shared/lib/downloadExampleFile";

function getImageDimensions(ratio: string) {
  if (ratio === "16:9") return { height: 900, width: 1600 };
  if (ratio === "4:3") return { height: 900, width: 1200 };
  return { height: 1024, width: 1024 };
}

export function downloadCreationResult({
  candidate,
  ratio,
  title,
  type,
}: {
  candidate: number;
  ratio: string;
  title: string;
  type: StudioType;
}) {
  const candidateLabel = String(candidate + 1);
  if (type === "image") {
    const { height, width } = getImageDimensions(ratio);
    const fontSize = Math.round(Math.min(width, height) * 0.04);
    const content = `<svg xmlns="http://www.w3.org/2000/svg" width="${String(width)}" height="${String(height)}" viewBox="0 0 ${String(width)} ${String(height)}"><rect width="100%" height="100%" fill="#F5EDE0"/><ellipse cx="50%" cy="73%" rx="39%" ry="10%" fill="#9A7659" opacity=".28"/><rect x="24%" y="28%" width="15%" height="42%" rx="48" fill="#C98A5C"/><rect x="42.5%" y="24%" width="15%" height="46%" rx="48" fill="#D4A5A5"/><rect x="61%" y="28%" width="15%" height="42%" rx="48" fill="#7F9D78"/><text x="50%" y="92%" text-anchor="middle" fill="#6B5344" font-size="${String(fontSize)}" font-family="sans-serif">${title} · 作品 ${candidateLabel}</text></svg>`;
    downloadExampleFile(
      `${title}_作品${candidateLabel}.svg`,
      content,
      "image/svg+xml;charset=utf-8",
    );
    return;
  }
  if (type === "video") {
    downloadExampleFile(
      `${title}_作品${candidateLabel}_预览说明.txt`,
      `${title}视频预览说明\n作品：${candidateLabel}\n画幅：${ratio}\n可用来查看镜头、时长和画面。`,
    );
    return;
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
}
