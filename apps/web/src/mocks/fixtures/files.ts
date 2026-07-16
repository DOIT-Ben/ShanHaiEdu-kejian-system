import type { FileObject } from "@/shared/api/types";
import { getDb, nextId } from "../db";

/** 生成确定性的 SVG 占位插图（Mock 图片资产的可视表示）。 */
export function svgDataUri(label: string, hueSeed: number, sub = ""): string {
  const hue = (hueSeed * 47) % 360;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="hsl(${hue},70%,88%)"/>
    <stop offset="1" stop-color="hsl(${(hue + 40) % 360},60%,76%)"/>
  </linearGradient></defs>
  <rect width="640" height="360" fill="url(#g)"/>
  <circle cx="540" cy="70" r="46" fill="hsl(${hue},65%,68%)" opacity="0.7"/>
  <rect x="40" y="230" width="200" height="16" rx="8" fill="hsl(${hue},45%,60%)" opacity="0.6"/>
  <text x="40" y="120" font-family="sans-serif" font-size="34" font-weight="600" fill="hsl(${hue},50%,28%)">${label}</text>
  <text x="40" y="170" font-family="sans-serif" font-size="20" fill="hsl(${hue},35%,38%)">${sub}</text>
</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export function makeFileObject(input: {
  fileName: string;
  mimeType: string;
  sizeBytes: number;
  previewUrl?: string | null;
}): FileObject {
  const db = getDb();
  const id = nextId(db, "file");
  db.fileNames.set(id, input.fileName);
  return {
    file_object_id: id,
    file_name: input.fileName,
    mime_type: input.mimeType,
    size_bytes: input.sizeBytes,
    preview_url: input.previewUrl ?? null,
  };
}

export function makeImageFileObject(label: string, hueSeed: number, sub = ""): FileObject {
  return makeFileObject({
    fileName: `${label}.svg`,
    mimeType: "image/svg+xml",
    sizeBytes: 24_000 + hueSeed * 130,
    previewUrl: svgDataUri(label, hueSeed, sub),
  });
}
