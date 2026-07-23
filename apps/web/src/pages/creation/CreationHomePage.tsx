import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import { studioRegistry } from "@/features/creation-studio/registry";
import { CreatorRail } from "@/features/navigation/CreatorRail";

const studios = [
  { config: studioRegistry.image, detail: "情境图、教具、数学关系图", ratio: "4:3" },
  { config: studioRegistry.video, detail: "导入片段、镜头和故事画面", ratio: "16:9" },
  { config: studioRegistry.presentation, detail: "封面、知识页和课堂练习", ratio: "16:9" },
];

export function CreationHomePage() {
  return (
    <div className="min-h-[calc(100dvh-var(--sh-topbar-height))] bg-[var(--sh-surface-canvas)] px-4 py-5 md:px-6">
      <div className="mx-auto grid max-w-[1380px] gap-5 xl:grid-cols-[220px_minmax(0,1fr)]">
        <CreatorRail className="sticky top-[calc(var(--sh-topbar-height)+20px)] hidden h-fit xl:block" />
        <main className="min-w-0">
          <header className="border-b border-[var(--sh-line-subtle)] pb-5">
            <p className="text-sm font-semibold text-[var(--sh-brand-600)]">创作中心</p>
            <h1 className="mt-1 text-2xl font-semibold text-[var(--sh-ink-strong)] md:text-[28px]">
              今天想创作什么
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--sh-ink-muted)]">
              独立制作教学图片、课堂视频或 PPT，不需要先进入项目。
            </p>
          </header>

          <section aria-label="选择创作台" className="mt-5 grid gap-4 lg:grid-cols-3">
            {studios.map(({ config, detail, ratio }, index) => {
              const Icon = config.icon;
              return (
                <Link
                  className="group overflow-hidden rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)] transition-[transform,box-shadow] hover:-translate-y-0.5 hover:shadow-[var(--sh-shadow-hover)]"
                  key={config.type}
                  to={`/app/creation/${config.path}`}
                >
                  <CreativeResultVisual
                    loading={index === 0 ? "eager" : "lazy"}
                    ratio={ratio}
                    type={config.type}
                    variant={index === 2 ? 1 : 0}
                  />
                  <div className="flex items-center gap-3 p-4">
                    <span className="grid size-10 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]">
                      <Icon aria-hidden="true" className="size-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <strong className="block text-[var(--sh-ink-strong)]">
                        {config.entryTitle}
                      </strong>
                      <span className="mt-0.5 block text-xs text-[var(--sh-ink-muted)]">
                        {detail}
                      </span>
                    </span>
                    <ArrowRight
                      aria-hidden="true"
                      className="size-4 shrink-0 text-[var(--sh-brand-700)] transition-transform group-hover:translate-x-1"
                    />
                  </div>
                </Link>
              );
            })}
          </section>
        </main>
      </div>
    </div>
  );
}
