import { ArrowRight, Check, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import brandMark from "@/assets/brand/brand-mark.svg";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import { Button } from "@/shared/ui/Button";

export function HomeBrandHero({
  continueTo,
  hasProject,
}: {
  continueTo: string;
  hasProject: boolean;
}) {
  return (
    <section
      aria-labelledby="home-brand-title"
      className="relative isolate grid min-h-[276px] overflow-hidden rounded-[var(--sh-radius-lg)] bg-[image:var(--sh-hero-gradient)] lg:min-h-[260px] lg:grid-cols-[minmax(0,0.92fr)_minmax(440px,1.08fr)]"
    >
      <div className="relative z-10 flex flex-col justify-center px-6 py-7 md:px-8 lg:px-10 lg:py-5">
        <p className="flex items-center gap-2 text-sm font-semibold text-[var(--sh-brand-600)]">
          <span className="grid size-7 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-elevated)]/90 p-0.5 shadow-[var(--sh-shadow-card)]">
            <img alt="" aria-hidden="true" className="size-full" src={brandMark} />
          </span>
          山海教育 · 课堂创作空间
        </p>
        <h1
          className="mt-2 max-w-[560px] text-[clamp(2rem,3.2vw,2.9rem)] font-semibold leading-[1.16] text-[var(--sh-ink-strong)]"
          id="home-brand-title"
        >
          从一份教材，到一节孩子愿意听的好课
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--sh-ink-muted)] md:text-[15px]">
          教案、课件、课堂图片和导入视频在同一条创作路径中自然完成。你只需要关注课堂。
        </p>
        <div className="mt-5 flex flex-wrap gap-2.5">
          {hasProject ? (
            <>
              <Button asChild>
                <Link to={continueTo}>
                  继续当前课件
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
              <Button asChild variant="secondary">
                <Link to="/app/projects/new">
                  <Upload aria-hidden="true" />
                  新建课件
                </Link>
              </Button>
            </>
          ) : (
            <>
              <Button asChild>
                <Link to="/app/projects/new">
                  <Upload aria-hidden="true" />
                  上传教材开始制作
                </Link>
              </Button>
              <Button asChild variant="secondary">
                <Link to="/app/projects">
                  浏览项目空间
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </>
          )}
        </div>
      </div>

      <div
        aria-label="课堂作品组合预览"
        className="relative min-h-[240px] overflow-hidden lg:min-h-[260px]"
        data-testid="brand-hero-preview"
      >
        <div className="absolute inset-y-5 right-[5%] w-[82%] rotate-[1deg] overflow-hidden rounded-[var(--sh-radius-md)] border-[6px] border-[var(--sh-surface-elevated)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-floating)]">
          <CreativeResultVisual type="presentation" variant={0} />
        </div>
        <div className="absolute bottom-3 right-[4%] w-[29%] -rotate-[3deg] overflow-hidden rounded-[var(--sh-radius-md)] border-4 border-[var(--sh-surface-elevated)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-floating)]">
          <CreativeResultVisual ratio="4:3" type="image" variant={0} />
        </div>
        <div className="absolute bottom-4 left-[4%] hidden items-center gap-2 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]/92 px-3 py-2 text-xs font-semibold text-[var(--sh-ink-strong)] shadow-[var(--sh-shadow-card)] backdrop-blur-sm sm:flex">
          <span className="grid size-7 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]">
            <Check aria-hidden="true" className="size-4" />
          </span>
          教案、课件和课堂素材，一起准备
        </div>
      </div>
    </section>
  );
}
