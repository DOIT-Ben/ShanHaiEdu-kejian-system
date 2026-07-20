import brandMark from "@/assets/brand/brand-mark.svg";

type HomeBrandHeroProps = {
  hasProject: boolean;
  heading?: string;
  lessonTitle?: string;
  projectTitle?: string;
};

/** A compact context header; task actions belong to the task summary below. */
export function HomeBrandHero({
  hasProject,
  heading,
  lessonTitle,
  projectTitle,
}: HomeBrandHeroProps) {
  const title = heading ?? (hasProject ? (projectTitle ?? "当前项目") : "开始第一份课堂项目");

  return (
    <section
      aria-labelledby="home-brand-title"
      className="border-b border-[var(--sh-line-default)] pb-3"
    >
      <p className="flex items-center gap-2 text-xs font-semibold text-[var(--sh-brand-600)]">
        <span className="grid size-6 place-items-center rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-1 shadow-[var(--sh-shadow-card)]">
          <img alt="" aria-hidden="true" className="size-full" src={brandMark} />
        </span>
        山海教育 · 课堂创作空间
      </p>
      <h1
        className="sh-display-type mt-2 max-w-[720px] truncate text-[clamp(1.45rem,2.6vw,2.1rem)] font-semibold leading-tight text-[var(--sh-ink-strong)]"
        id="home-brand-title"
      >
        {title}
      </h1>
      <p className="mt-1 truncate text-sm text-[var(--sh-ink-muted)]">
        {hasProject
          ? (lessonTitle ?? "课时信息将在进入项目后显示")
          : "上传教材后，先安排课时，再继续完成教案和课堂作品。"}
      </p>
    </section>
  );
}
