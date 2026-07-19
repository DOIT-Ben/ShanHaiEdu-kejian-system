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
  const label = topic
    ? `果汁标签课堂示例，仅作“${topic}”画面节奏参考；当前课题视频尚未生成`
    : `果汁标签侦探：${scene.label}，关键帧示意，视频尚未生成`;

  return (
    <div
      aria-label={label}
      className={`group relative aspect-video overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-player)] shadow-[var(--sh-shadow-card)] ${compact ? "ring-1 ring-[var(--sh-line-subtle)]" : ""}`}
      role="img"
    >
      <img
        alt=""
        aria-hidden="true"
        className="size-full object-cover transition-transform duration-[var(--sh-duration-slow)] group-hover:scale-[1.015]"
        decoding="async"
        src={scene.source}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-[var(--sh-surface-inverse)]/42 via-transparent to-transparent" />
      <span
        className={`absolute left-2 top-2 rounded-full bg-[var(--sh-surface-elevated)]/92 font-semibold text-[var(--sh-brand-700)] shadow-[var(--sh-shadow-card)] backdrop-blur-sm ${compact ? "px-1.5 py-0.5 text-[9px]" : "px-2.5 py-1 text-xs"}`}
      >
        {topic ? "课堂示例参考 · 当前课题尚未生成" : "关键帧示意 · 视频尚未生成"}
      </span>
      {!compact ? (
        <p className="absolute bottom-3 left-4 max-w-[calc(100%-2rem)] truncate text-xs font-medium text-white">
          {topic ? `果汁标签课堂示例 · 非“${topic}”生成结果` : `${scene.label} · 关键帧参考`}
        </p>
      ) : null}
    </div>
  );
}
