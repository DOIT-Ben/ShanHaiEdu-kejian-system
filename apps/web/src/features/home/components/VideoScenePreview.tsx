import { Play } from "lucide-react";

export function VideoScenePreview({ variant = 0, topic }: { variant?: number; topic?: string }) {
  const source =
    variant % 2 === 0
      ? "/assets/creation/video-label-detective.svg"
      : "/assets/creation/video-classroom-question.svg";

  return (
    <div
      aria-label="课堂导入视频画面预览"
      className="group relative aspect-video overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-player)] shadow-[var(--sh-shadow-card)]"
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
          className="size-full object-cover transition-transform duration-[var(--sh-duration-slow)] group-hover:scale-[1.015]"
          decoding="async"
          src={source}
        />
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-[var(--sh-surface-inverse)]/42 via-transparent to-transparent" />
      <div className="absolute inset-0 grid place-items-center">
        <span className="grid size-12 place-items-center rounded-full bg-[var(--sh-surface-elevated)]/94 text-[var(--sh-brand-700)] shadow-[var(--sh-shadow-floating)] backdrop-blur-sm transition-transform duration-[var(--sh-duration-fast)] group-hover:scale-105">
          <Play aria-hidden="true" className="ml-0.5 size-5 fill-current" />
        </span>
      </div>
      <p className="absolute bottom-3 left-4 text-xs font-medium text-white">
        {topic ? `${topic} · 课堂导入预览` : "一杯果汁里的数学秘密 · 00:42"}
      </p>
    </div>
  );
}
