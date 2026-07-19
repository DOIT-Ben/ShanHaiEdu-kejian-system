import { ArrowRight, BookOpenCheck, Image, PlaySquare, Presentation, Upload } from "lucide-react";
import { Link, NavLink } from "react-router-dom";
import { cn } from "@/shared/lib/cn";

const steps = [
  {
    detail: "确定知识点和课时范围",
    icon: Upload,
    label: "上传一份教材",
    to: "/app/projects/new",
  },
  {
    detail: "教案、故事和课堂节奏逐步确认",
    icon: BookOpenCheck,
    label: "审看课堂内容",
    to: "/app/projects",
  },
  {
    detail: "按需要制作图片、视频或课件",
    icon: Presentation,
    label: "完成课堂作品",
    to: "/app/creation",
  },
];

const quickEntries = [
  { icon: Image, label: "图片", to: "/app/creation/images" },
  { icon: PlaySquare, label: "视频", to: "/app/creation/videos" },
  { icon: Presentation, label: "PPT", to: "/app/creation/presentations" },
];

export function CreatorRail({ className }: { className?: string }) {
  return (
    <aside
      aria-label="创作向导"
      className={cn(
        "rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3 shadow-[var(--sh-shadow-card)]",
        className,
      )}
    >
      <div className="px-3 pb-3 pt-2">
        <p className="text-xs font-medium tracking-[0.12em] text-[var(--sh-brand-600)]">
          我的创作桌
        </p>
        <p className="mt-1 text-lg font-semibold text-[var(--sh-ink-strong)]">三步完成一节好课</p>
      </div>

      <ol className="space-y-1.5">
        {steps.map(({ detail, icon: Icon, label, to }, index) => (
          <li key={to}>
            <Link
              className="group flex gap-3 rounded-[var(--sh-radius-md)] px-3 py-2.5 transition-[background-color,transform] duration-[var(--sh-duration-fast)] hover:translate-x-0.5 hover:bg-[var(--sh-surface-soft)]"
              to={to}
            >
              <span className="relative grid size-9 shrink-0 place-items-center rounded-full bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]">
                <Icon aria-hidden="true" className="size-4" />
                <span className="absolute -left-1 -top-1 grid size-4 place-items-center rounded-full bg-[var(--sh-brand-600)] text-[10px] font-bold text-white">
                  {index + 1}
                </span>
              </span>
              <span className="min-w-0 flex-1">
                <strong className="block text-sm text-[var(--sh-ink-strong)]">{label}</strong>
                <span className="mt-0.5 block text-xs leading-4 text-[var(--sh-ink-muted)]">
                  {detail}
                </span>
              </span>
              <ArrowRight
                aria-hidden="true"
                className="mt-2 size-3.5 shrink-0 text-[var(--sh-brand-600)] transition-transform group-hover:translate-x-0.5"
              />
            </Link>
          </li>
        ))}
      </ol>

      <div className="mx-3 my-3 h-px bg-[var(--sh-line-subtle)]" />
      <p className="px-3 text-xs font-semibold text-[var(--sh-ink-muted)]">直接创作</p>
      <nav aria-label="快速创作" className="mt-2 grid grid-cols-3 gap-2 px-1">
        {quickEntries.map(({ icon: Icon, label, to }) => (
          <NavLink
            className={({ isActive }) =>
              cn(
                "grid min-h-14 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] px-1 text-xs font-medium text-[var(--sh-ink-default)] transition-[background-color,color,transform] duration-[var(--sh-duration-fast)] hover:-translate-y-px hover:bg-[var(--sh-brand-50)]",
                isActive && "bg-[var(--sh-brand-100)] text-[var(--sh-brand-900)]",
              )
            }
            key={to}
            to={to}
          >
            <span className="grid place-items-center gap-1">
              <Icon aria-hidden="true" className="size-4" />
              {label}
            </span>
          </NavLink>
        ))}
      </nav>

      <div className="mt-4 overflow-hidden rounded-[var(--sh-radius-md)] bg-[var(--sh-brand-50)] p-3">
        <p className="text-xs font-semibold text-[var(--sh-brand-700)]">给老师的小提示</p>
        <p className="mt-1 text-sm font-medium leading-5 text-[var(--sh-ink-strong)]">
          不确定从哪里开始，就先上传教材；每一步都会告诉你接下来做什么。
        </p>
      </div>
    </aside>
  );
}
