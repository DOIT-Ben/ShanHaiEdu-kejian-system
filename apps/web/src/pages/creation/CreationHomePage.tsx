import { ArrowRight, Clock3, PackageOpen } from "lucide-react";
import { Link } from "react-router-dom";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import { RecentCreationRail } from "@/features/creation-studio/RecentCreationRail";
import { studioRegistry } from "@/features/creation-studio/registry";
import { CreatorRail } from "@/features/navigation/CreatorRail";
import { demoLessonId, demoProjectId } from "@/shared/data/mockData";
import { taskItems } from "@/shared/data/mockData";
import { StatusBadge } from "@/shared/ui/StatusBadge";

const studios = [
  { config: studioRegistry.image, ratio: "4:3", variant: 0 },
  { config: studioRegistry.video, ratio: "16:9", variant: 0 },
  { config: studioRegistry.presentation, ratio: "16:9", variant: 1 },
];

export function CreationHomePage() {
  return (
    <div className="min-h-[calc(100vh-var(--sh-topbar-height))] bg-[image:var(--sh-workspace-gradient)] px-4 py-5 md:px-5">
      <div className="mx-auto grid max-w-[1540px] gap-5 xl:grid-cols-[240px_minmax(0,1fr)_300px]">
        <CreatorRail className="sticky top-[calc(var(--sh-topbar-height)+20px)] hidden h-[calc(100vh-var(--sh-topbar-height)-40px)] xl:block" />

        <div className="min-w-0">
          <header className="flex flex-col gap-3 rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]/76 px-5 py-4 shadow-[var(--sh-shadow-card)] backdrop-blur-sm sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-medium text-[var(--sh-brand-600)]">创作中心</p>
              <h1 className="mt-0.5 text-[28px] font-semibold leading-tight">今天想创作什么</h1>
              <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
                选一种作品，画面、要求和下一步都在同一张创作桌上。
              </p>
            </div>
            <div className="rounded-[var(--sh-radius-md)] bg-[var(--sh-brand-50)] px-3 py-2.5">
              <div>
                <p className="text-xs font-medium text-[var(--sh-ink-strong)]">
                  第一次使用？建议先画一张教学图片
                </p>
                <Link
                  className="mt-0.5 inline-flex items-center gap-1 text-xs font-semibold text-[var(--sh-brand-700)]"
                  to="/app/creation/images"
                >
                  去画一张
                  <ArrowRight aria-hidden="true" className="size-3" />
                </Link>
              </div>
            </div>
          </header>

          <section aria-label="选择创作台" className="mt-5 grid gap-4 sm:grid-cols-2">
            {studios.map(({ config, ratio, variant }, index) => {
              const Icon = config.icon;
              return (
                <Link
                  className={`group relative overflow-hidden rounded-[var(--sh-radius-lg)] border-[5px] border-[var(--sh-surface-elevated)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-floating)] transition-[transform,box-shadow] duration-[var(--sh-duration-normal)] hover:-translate-y-1 hover:shadow-[var(--sh-shadow-modal)] ${index === 0 ? "sm:row-span-2" : ""}`}
                  key={config.type}
                  to={`/app/creation/${config.path}`}
                >
                  <CreativeResultVisual
                    loading={index === 0 ? "eager" : "lazy"}
                    ratio={ratio}
                    type={config.type}
                    variant={variant}
                  />
                  <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 bg-gradient-to-t from-[var(--sh-surface-inverse)]/90 via-[var(--sh-surface-inverse)]/42 to-transparent px-4 pb-4 pt-14 text-white">
                    <span className="flex min-w-0 items-center gap-3">
                      <span className="grid size-10 shrink-0 place-items-center rounded-[var(--sh-radius-md)] bg-white/18 backdrop-blur-sm">
                        <Icon aria-hidden="true" className="size-5" />
                      </span>
                      <span className="min-w-0">
                        <strong className="block truncate text-base text-white">
                          {config.entryTitle}
                        </strong>
                        <span className="mt-0.5 block truncate text-xs text-white/82">
                          {index === 0
                            ? "情境图、教具、数学关系图"
                            : index === 1
                              ? "导入片段、镜头和故事画面"
                              : "封面、知识页和课堂练习"}
                        </span>
                      </span>
                    </span>
                    <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[var(--sh-surface-elevated)] text-[var(--sh-brand-700)] transition-transform group-hover:translate-x-1">
                      <ArrowRight aria-hidden="true" className="size-4" />
                    </span>
                  </div>
                </Link>
              );
            })}
          </section>

          <section className="mt-5 grid gap-4 lg:grid-cols-[1fr_0.72fr]">
            <Link
              className="group flex items-center gap-4 rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4 shadow-[var(--sh-shadow-card)] transition-[transform,box-shadow] hover:-translate-y-0.5 hover:shadow-[var(--sh-shadow-hover)]"
              to={`/app/creation/batches/video-assets-${demoProjectId}--lesson--${demoLessonId}?sourceProjectId=${demoProjectId}&lessonId=${demoLessonId}`}
            >
              <span className="grid size-12 shrink-0 place-items-center rounded-[var(--sh-radius-md)] bg-[var(--sh-success-soft)] text-[var(--sh-success)]">
                <PackageOpen aria-hidden="true" className="size-5" />
              </span>
              <span className="min-w-0 flex-1">
                <strong className="block truncate text-[var(--sh-ink-strong)]">
                  果汁标签侦探 · 还有 4 个画面
                </strong>
                <span className="mt-1 flex items-center gap-1.5 text-xs text-[var(--sh-ink-muted)]">
                  <Clock3 aria-hidden="true" className="size-3.5" />
                  来自“认识百分数”第 1 课时
                </span>
              </span>
              <ArrowRight
                aria-hidden="true"
                className="size-5 shrink-0 text-[var(--sh-brand-700)] transition-transform group-hover:translate-x-1"
              />
            </Link>
            <div className="flex items-center gap-3 rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4 shadow-[var(--sh-shadow-card)]">
              <StatusBadge status={taskItems[1]?.status ?? "queued"} />
              <span className="min-w-0">
                <strong className="block truncate text-sm text-[var(--sh-ink-strong)]">
                  {taskItems[1]?.title ?? "课堂作品正在制作"}
                </strong>
                <span className="mt-0.5 block truncate text-xs text-[var(--sh-ink-muted)]">
                  完成后会放进最近作品
                </span>
              </span>
            </div>
          </section>
        </div>

        <RecentCreationRail className="h-fit xl:sticky xl:top-[calc(var(--sh-topbar-height)+20px)]" />
      </div>
    </div>
  );
}
