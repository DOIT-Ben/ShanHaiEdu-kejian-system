export function PercentSlidePreview({
  compact = false,
  topic,
  variant = 0,
}: {
  compact?: boolean;
  topic?: string;
  variant?: number;
}) {
  const source =
    variant % 2 === 0
      ? "/assets/creation/slide-percent-cover.svg"
      : "/assets/creation/slide-percent-grid.svg";

  return (
    <div
      aria-label="百分数课堂课件页面预览"
      className={`relative aspect-video overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-artifact-paper)] shadow-[var(--sh-shadow-card)] ${compact ? "ring-1 ring-[var(--sh-line-subtle)]" : ""}`}
      role="img"
    >
      {topic ? (
        <div className="flex size-full flex-col justify-center bg-[var(--sh-artifact-paper)] px-[10%] text-[var(--sh-artifact-ink)]">
          <p className="text-xs font-semibold text-[var(--sh-art-green)]">小学数学课堂</p>
          <p className="mt-3 text-[clamp(1rem,2.8vw,2.3rem)] font-bold">{topic}</p>
          <div className="mt-5 grid grid-cols-6 gap-1">
            {Array.from({ length: 18 }, (_, index) => (
              <span
                className={`aspect-square rounded-sm ${index < 9 ? "bg-[var(--sh-art-gold)]" : "bg-[var(--sh-art-paper-green)]"}`}
                key={index}
              />
            ))}
          </div>
        </div>
      ) : (
        <img alt="" className="size-full object-cover" decoding="async" src={source} />
      )}
    </div>
  );
}
