import { Play } from "lucide-react";
import { creationVideoShotAssets } from "@/assets/creation/catalog";

const demoVideoScenes = [
  {
    label: "课堂里出现三瓶果汁",
    source: creationVideoShotAssets[0],
  },
  {
    label: "学生近距离观察果汁标签",
    source: creationVideoShotAssets[1],
  },
  {
    label: "学生举手分享自己的发现",
    source: creationVideoShotAssets[2],
  },
  {
    label: "画面停在等待回答的课堂首问",
    source: creationVideoShotAssets[3],
  },
] as const;

function getDemoScene(variant: number) {
  const index =
    ((variant % demoVideoScenes.length) + demoVideoScenes.length) % demoVideoScenes.length;
  return demoVideoScenes[index] as (typeof demoVideoScenes)[number];
}

export function getDemoVideoSceneSource(variant: number) {
  return getDemoScene(variant).source;
}

export function VideoScenePreview({
  compact = false,
  topic,
  variant = 0,
}: {
  compact?: boolean;
  topic?: string;
  variant?: number;
}) {
  const scene = getDemoScene(variant);
  const label = topic ? `${topic}课堂导入画面预览` : `果汁标签侦探：${scene.label}`;

  return (
    <div
      aria-label={label}
      className={`group relative aspect-video overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-player)] shadow-[var(--sh-shadow-card)] ${compact ? "ring-1 ring-[var(--sh-line-subtle)]" : ""}`}
      role="img"
    >
      {topic ? (
        <div
          className={`flex size-full flex-col justify-center px-[10%] text-white ${variant % 3 === 1 ? "bg-[var(--sh-brand-900)]" : variant % 3 === 2 ? "bg-[var(--sh-art-green)]" : "bg-[var(--sh-art-navy)]"}`}
          data-video-style-variant={variant % 3}
        >
          <p className="text-xs text-[var(--sh-artifact-on-dark-muted)]">课堂导入预览</p>
          <p className="mt-2 text-[clamp(1rem,2.8vw,2.2rem)] font-bold">{topic}</p>
          <div className="mt-4 flex gap-2">
            {[0, 1, 2].map((item) => (
              <span className="h-2 flex-1 rounded-full bg-[var(--sh-art-gold)]/80" key={item} />
            ))}
          </div>
        </div>
      ) : (
        <img
          alt=""
          aria-hidden="true"
          className="size-full object-cover transition-transform duration-[var(--sh-duration-slow)] group-hover:scale-[1.015]"
          decoding="async"
          src={scene.source}
        />
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-[var(--sh-surface-inverse)]/42 via-transparent to-transparent" />
      <div className="absolute inset-0 grid place-items-center">
        <span
          className={`grid place-items-center rounded-full bg-[var(--sh-surface-elevated)]/94 text-[var(--sh-brand-700)] shadow-[var(--sh-shadow-floating)] backdrop-blur-sm transition-transform duration-[var(--sh-duration-fast)] group-hover:scale-105 ${compact ? "size-7" : "size-12"}`}
        >
          <Play
            aria-hidden="true"
            className={`ml-0.5 fill-current ${compact ? "size-3" : "size-5"}`}
          />
        </span>
      </div>
      {!compact ? (
        <p className="absolute bottom-3 left-4 max-w-[calc(100%-2rem)] truncate text-xs font-medium text-white">
          {topic ? `${topic} · 课堂导入预览` : `${scene.label} · 示例画面`}
        </p>
      ) : null}
    </div>
  );
}
