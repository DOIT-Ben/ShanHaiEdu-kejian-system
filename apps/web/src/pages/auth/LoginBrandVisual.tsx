import brandMark from "@/assets/brand/brand-mark.svg";
import { creationVideoShotAssets } from "@/assets/creation/catalog";
import emptyProjectDesk from "@/assets/illustrations/empty-project-desk.webp";
import { cn } from "@/shared/lib/cn";

export function LoginBrandLockup({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <span className="grid size-11 shrink-0 place-items-center rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-1.5 shadow-[var(--sh-shadow-card)]">
        <img alt="" aria-hidden="true" className="size-full" src={brandMark} />
      </span>
      <span>
        <strong className="block text-sm font-semibold text-[var(--sh-ink-strong)]">
          山海教育
        </strong>
        <span className="mt-0.5 block text-xs text-[var(--sh-ink-muted)]">课堂创作台</span>
      </span>
    </div>
  );
}

export function LoginVisualPanel() {
  return (
    <section className="relative hidden min-h-screen overflow-hidden bg-[var(--sh-surface-inverse)] px-8 py-7 text-[var(--sh-artifact-on-dark)] lg:flex lg:items-center xl:px-12">
      <div className="relative mx-auto w-full max-w-[680px]">
        <div className="flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-[var(--sh-radius-md)] bg-[var(--sh-artifact-paper)]/92 p-1.5 shadow-[var(--sh-shadow-floating)]">
            <img alt="" aria-hidden="true" className="size-full" src={brandMark} />
          </span>
          <span>
            <strong className="block text-sm font-semibold text-[var(--sh-artifact-on-dark)]">
              山海教育
            </strong>
            <span className="mt-0.5 block text-xs text-[var(--sh-artifact-on-dark-muted)]">
              课堂创作台
            </span>
          </span>
        </div>

        <p className="sh-display-type mt-6 max-w-xl text-[clamp(2rem,3.3vw,2.7rem)] font-semibold leading-[1.18] text-[var(--sh-artifact-on-dark)]">
          把教材变成完整的课堂作品
        </p>
        <p className="mt-3 max-w-lg text-sm leading-6 text-[var(--sh-artifact-on-dark-muted)]">
          在同一处准备课时、教案、课件和课堂素材，把更多时间留给孩子。
        </p>

        <figure className="relative mt-7 pr-10">
          <div className="overflow-hidden rounded-[var(--sh-radius-lg)] border-[6px] border-[var(--sh-artifact-paper)]/92 bg-[var(--sh-artifact-paper)] shadow-[var(--sh-shadow-modal)]">
            <img
              alt="老师带领两名学生观察数学材料的温暖课堂"
              className="aspect-[16/9] w-full object-cover object-[50%_45%]"
              decoding="async"
              fetchPriority="high"
              loading="eager"
              src={creationVideoShotAssets[0]}
            />
          </div>
          <div className="absolute -bottom-4 right-0 w-[36%] overflow-hidden rounded-[var(--sh-radius-md)] border-4 border-[var(--sh-artifact-paper)] bg-[var(--sh-artifact-paper)] shadow-[var(--sh-shadow-floating)]">
            <img
              alt=""
              aria-hidden="true"
              className="aspect-[3/2] w-full object-cover"
              decoding="async"
              loading="eager"
              src={emptyProjectDesk}
            />
          </div>
        </figure>
      </div>
    </section>
  );
}
