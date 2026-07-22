import { ArrowLeft, BookOpen, Waves } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

export function RuntimeUnavailablePage({
  description = "这项能力正在接入你的课堂数据，现阶段不会用演示内容代替真实结果。",
  title = "这里还没有可用内容",
}: {
  description?: string;
  title?: string;
}) {
  const location = useLocation();
  return (
    <div className="mx-auto max-w-[960px] px-4 py-8 md:px-6 lg:px-8">
      <FocusPageHeader description={description} title={title} />
      <section className="mt-8 rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-8 text-center shadow-[var(--sh-shadow-card)]">
        <span className="mx-auto grid size-14 place-items-center rounded-full bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]">
          <Waves aria-hidden="true" className="size-7" />
        </span>
        <h2 className="mt-5 text-xl font-semibold text-[var(--sh-ink-strong)]">先从项目开始</h2>
        <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-[var(--sh-ink-muted)]">
          项目列表会展示已经保存的课程。准备好后，你可以从那里继续课堂制作。
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Link className={buttonVariants()} to="/app/projects">
            <BookOpen aria-hidden="true" />
            查看项目
          </Link>
          {location.pathname !== "/app" ? (
            <Link className={buttonVariants({ variant: "secondary" })} to="/app">
              <ArrowLeft aria-hidden="true" />
              返回首页
            </Link>
          ) : null}
        </div>
      </section>
    </div>
  );
}
