import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { LoaderCircle } from "lucide-react";
import { useState } from "react";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import { presentationPreviewPages, type StudioType } from "@/features/creation-studio/model";

function PresentationResult({ variation }: { variation: number }) {
  const [page, setPage] = useState(2);
  return (
    <div className="flex flex-col gap-3">
      <div className="mx-auto w-full max-w-[960px]">
        <CreativeResultVisual page={page} type="presentation" variant={variation} />
        <p className="mt-2 text-center text-xs text-[var(--sh-ink-muted)]">
          第 {page + 1} 页 · {presentationPreviewPages[page]}
        </p>
      </div>
      <aside aria-label="PPT 页面" className="mx-auto flex max-w-full gap-2 overflow-x-auto pb-1">
        {presentationPreviewPages.map((label, index) => (
          <button
            aria-pressed={page === index}
            className={`w-24 shrink-0 rounded-[var(--sh-radius-sm)] border bg-[var(--sh-surface-elevated)] p-1.5 text-left transition-[border-color,box-shadow] duration-[var(--sh-duration-fast)] ${page === index ? "border-[var(--sh-brand-500)] ring-2 ring-[var(--sh-brand-100)]" : "border-[var(--sh-line-subtle)]"}`}
            key={label}
            onClick={() => setPage(index)}
            type="button"
          >
            <CreativeResultVisual page={index} type="presentation" variant={variation} />
            <span className="mt-1 block truncate text-xs font-medium text-[var(--sh-ink-strong)]">
              {index + 1}. {label}
            </span>
          </button>
        ))}
      </aside>
    </div>
  );
}

function ResultVisual({
  candidate,
  generation,
  ratio,
  type,
}: {
  candidate: number;
  generation: number;
  ratio: string;
  type: StudioType;
}) {
  const visualVariant = candidate + generation;
  return type === "presentation" ? (
    <PresentationResult variation={visualVariant} />
  ) : (
    <CreativeResultVisual ratio={ratio} type={type} variant={visualVariant % 3} />
  );
}

function RenderingVisual({
  candidate,
  generation,
  ratio,
  type,
}: {
  candidate: number;
  generation: number;
  ratio: string;
  type: StudioType;
}) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      animate={{ opacity: 1, scale: 1 }}
      className="relative overflow-hidden rounded-[var(--sh-radius-sm)]"
      initial={{ opacity: 0, scale: reduceMotion ? 1 : 0.985 }}
      transition={{ duration: reduceMotion ? 0 : 0.32, ease: [0.2, 0.8, 0.2, 1] }}
    >
      <div aria-hidden="true" className="scale-[1.02] opacity-35 blur-[2px]">
        <ResultVisual candidate={candidate} generation={generation} ratio={ratio} type={type} />
      </div>
      <div className="absolute inset-0 bg-[var(--sh-surface-inverse)]/35 backdrop-blur-[1px]" />
      {!reduceMotion ? (
        <motion.div
          animate={{ x: ["-130%", "260%"] }}
          aria-hidden="true"
          className="absolute inset-y-0 left-0 w-1/3 -skew-x-12 bg-white/35"
          transition={{ duration: 1.45, ease: "easeInOut", repeat: Infinity }}
        />
      ) : null}
      <div
        aria-live="polite"
        className="absolute inset-0 grid place-items-center px-4 text-center text-white"
        role="status"
      >
        <div>
          <span className="mx-auto grid size-11 place-items-center rounded-full bg-[var(--sh-surface-elevated)]/95 text-[var(--sh-brand-600)] shadow-[var(--sh-shadow-floating)]">
            <LoaderCircle
              aria-hidden="true"
              className="size-5 animate-spin motion-reduce:animate-none"
            />
          </span>
          <p className="mt-3 text-sm font-semibold">正在创作新作品</p>
          <p className="mt-1 text-xs text-white/80">正在把你的想法变成画面，请稍等</p>
        </div>
      </div>
    </motion.div>
  );
}

export function CreationResultCanvas({
  candidate,
  generation,
  ratio,
  running,
  type,
}: {
  candidate: number;
  generation: number;
  ratio: string;
  running: boolean;
  type: StudioType;
}) {
  const reduceMotion = useReducedMotion();
  return (
    <AnimatePresence initial={false} mode="wait">
      {running ? (
        <RenderingVisual
          candidate={candidate}
          generation={generation}
          key="rendering"
          ratio={ratio}
          type={type}
        />
      ) : (
        <motion.div
          animate={{ opacity: 1, scale: 1 }}
          initial={{ opacity: 0, scale: reduceMotion ? 1 : 0.985 }}
          key={`candidate-${String(candidate)}`}
          transition={{ duration: reduceMotion ? 0 : 0.32, ease: [0.2, 0.8, 0.2, 1] }}
        >
          <ResultVisual candidate={candidate} generation={generation} ratio={ratio} type={type} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
