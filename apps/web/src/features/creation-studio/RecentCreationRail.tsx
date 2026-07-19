import { ArrowUpRight, Clock3 } from "lucide-react";
import { Link } from "react-router-dom";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import { cn } from "@/shared/lib/cn";

const railLayoutClasses = {
  lg: {
    container:
      "md:grid md:grid-cols-[220px_minmax(0,1fr)] md:grid-rows-[auto_auto_1fr] md:gap-x-4 lg:block",
    details: "md:col-start-2 lg:mt-2",
    header: "md:col-start-2 lg:block",
    primary: "md:col-start-1 md:row-span-3 md:row-start-1 md:mt-0 lg:mt-4",
    secondary: "md:col-start-2 md:mt-3 md:self-end lg:mt-5",
  },
  xl: {
    container:
      "md:grid md:grid-cols-[220px_minmax(0,1fr)] md:grid-rows-[auto_auto_1fr] md:gap-x-4 xl:block",
    details: "md:col-start-2 xl:mt-2",
    header: "md:col-start-2 xl:block",
    primary: "md:col-start-1 md:row-span-3 md:row-start-1 md:mt-0 xl:mt-4",
    secondary: "md:col-start-2 md:mt-3 md:self-end xl:mt-5",
  },
} as const;

export function RecentCreationRail({
  className,
  stackAt = "xl",
}: {
  className?: string;
  stackAt?: keyof typeof railLayoutClasses;
}) {
  const layout = railLayoutClasses[stackAt];

  return (
    <aside
      aria-labelledby="recent-creations-title"
      className={cn(
        "rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4 shadow-[var(--sh-shadow-card)]",
        layout.container,
        className,
      )}
    >
      <div className={cn("flex items-center justify-between gap-3", layout.header)}>
        <div>
          <p className="text-xs font-medium text-[var(--sh-brand-600)]">作品夹</p>
          <h2 className="mt-0.5 text-xl font-semibold" id="recent-creations-title">
            最近作品
          </h2>
        </div>
      </div>

      <Link
        aria-label="打开果汁标签观察图"
        className={cn("group relative mt-4 block pb-4 pl-2 pt-2", layout.primary)}
        to="/app/creation/images"
      >
        <span className="absolute inset-x-7 bottom-0 top-5 rotate-[4deg] rounded-[var(--sh-radius-md)] bg-[var(--sh-accent-rose-soft)] shadow-[var(--sh-shadow-card)]" />
        <span className="absolute inset-x-4 bottom-2 top-3 -rotate-[2deg] rounded-[var(--sh-radius-md)] bg-[var(--sh-brand-100)] shadow-[var(--sh-shadow-card)]" />
        <span
          className="relative block overflow-hidden rounded-[var(--sh-radius-md)] border-[5px] border-[var(--sh-surface-elevated)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)] transition-transform duration-[var(--sh-duration-normal)] group-hover:-translate-y-0.5"
          data-testid="recent-primary-preview"
        >
          <CreativeResultVisual type="image" variant={0} />
        </span>
      </Link>
      <div className={cn("mt-2 flex items-start justify-between gap-3", layout.details)}>
        <div>
          <p className="font-semibold text-[var(--sh-ink-strong)]">果汁标签观察图</p>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-[var(--sh-ink-muted)]">
            <Clock3 aria-hidden="true" className="size-3.5" />
            12 分钟前
          </p>
        </div>
        <Link
          aria-label="继续编辑果汁标签观察图"
          className="grid size-9 shrink-0 place-items-center rounded-full border border-[var(--sh-line-default)] text-[var(--sh-brand-700)] hover:bg-[var(--sh-brand-50)]"
          to="/app/creation/images"
        >
          <ArrowUpRight aria-hidden="true" className="size-4" />
        </Link>
      </div>

      <div
        className={cn(
          "mt-5 grid grid-cols-2 gap-3 border-t border-[var(--sh-line-subtle)] pt-4",
          layout.secondary,
        )}
      >
        <Link className="group" to="/app/creation/presentations">
          <div className="overflow-hidden rounded-[var(--sh-radius-sm)] border-2 border-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)] transition-transform group-hover:-translate-y-0.5">
            <CreativeResultVisual page={2} type="presentation" variant={0} />
          </div>
          <p className="mt-2 truncate text-xs font-medium text-[var(--sh-ink-strong)]">
            百分数百格图
          </p>
        </Link>
        <Link className="group" to="/app/creation/videos">
          <div className="overflow-hidden rounded-[var(--sh-radius-sm)] border-2 border-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)] transition-transform group-hover:-translate-y-0.5">
            <CreativeResultVisual type="video" variant={1} />
          </div>
          <p className="mt-2 truncate text-xs font-medium text-[var(--sh-ink-strong)]">
            课堂首问关键帧
          </p>
        </Link>
      </div>
    </aside>
  );
}
