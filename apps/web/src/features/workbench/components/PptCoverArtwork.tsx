import type { ReactNode } from "react";
import { creationPptCoverAssets } from "@/assets/creation/catalog";

export const pptCoverOptions = [
  {
    id: 1,
    label: "百格光窗",
    source: creationPptCoverAssets[0],
  },
  {
    id: 2,
    label: "果汁标签",
    source: creationPptCoverAssets[1],
  },
  {
    id: 3,
    label: "课堂发现",
    source: creationPptCoverAssets[2],
  },
] as const;

export function getPptCoverOption(variant: number) {
  return pptCoverOptions.find((option) => option.id === variant) ?? pptCoverOptions[0];
}

export function PptCoverArtwork({
  children,
  demo,
  variant,
}: {
  children: ReactNode;
  demo: boolean;
  variant: number;
}) {
  const option = getPptCoverOption(variant);
  const generatedBackground =
    variant === 2
      ? "bg-[var(--sh-brand-900)]"
      : variant === 3
        ? "bg-[var(--sh-art-green)]"
        : "bg-[var(--sh-art-navy)]";

  return (
    <div
      aria-label={demo ? `${option.label}课件封面预览` : "课件封面预览"}
      className={`relative aspect-video overflow-hidden rounded-[var(--sh-radius-sm)] ${demo ? "bg-[var(--sh-artifact-paper)] text-[var(--sh-artifact-ink)]" : `${generatedBackground} text-white`}`}
      data-cover-variant={variant}
      role="group"
    >
      {demo ? (
        <>
          <img
            alt=""
            aria-hidden="true"
            className="absolute inset-0 size-full object-cover"
            decoding="async"
            src={option.source}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[var(--sh-artifact-paper)] via-[var(--sh-artifact-paper)]/90 to-transparent" />
        </>
      ) : (
        <>
          <span className="absolute -right-[7%] -top-[18%] size-[48%] rounded-full border border-white/10" />
          <span className="absolute bottom-[8%] right-[9%] h-1.5 w-[22%] rounded-full bg-[var(--sh-art-gold)]/75" />
        </>
      )}
      <div className="relative flex size-full max-w-[58%] flex-col justify-center px-[8%]">
        {children}
      </div>
    </div>
  );
}
