import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { cn } from "@/shared/lib/cn";

type HorizontalScrollAreaProps = {
  ariaLabel?: string;
  children: ReactNode;
  className?: string;
  hintTestId?: string;
  viewportClassName?: string;
};

export const HorizontalScrollArea = forwardRef<HTMLDivElement, HorizontalScrollAreaProps>(
  function HorizontalScrollArea(
    { ariaLabel, children, className, hintTestId, viewportClassName },
    forwardedRef,
  ) {
    const viewportRef = useRef<HTMLDivElement>(null);
    const [edges, setEdges] = useState({ left: false, right: false });
    useImperativeHandle(forwardedRef, () => viewportRef.current as HTMLDivElement, []);

    const updateEdges = useCallback(() => {
      const viewport = viewportRef.current;
      if (!viewport) return;
      setEdges({
        left: viewport.scrollLeft > 2,
        right: viewport.scrollLeft + viewport.clientWidth < viewport.scrollWidth - 2,
      });
    }, []);

    useEffect(() => {
      const viewport = viewportRef.current;
      if (!viewport) return;
      const frame = requestAnimationFrame(updateEdges);
      const resizeObserver =
        typeof ResizeObserver === "undefined" ? null : new ResizeObserver(updateEdges);
      const observeContents = () => {
        resizeObserver?.observe(viewport);
        for (const child of viewport.children) resizeObserver?.observe(child);
        updateEdges();
      };
      observeContents();
      const mutationObserver =
        typeof MutationObserver === "undefined" ? null : new MutationObserver(observeContents);
      mutationObserver?.observe(viewport, { childList: true, subtree: true });
      window.addEventListener("resize", updateEdges);
      return () => {
        cancelAnimationFrame(frame);
        resizeObserver?.disconnect();
        mutationObserver?.disconnect();
        window.removeEventListener("resize", updateEdges);
      };
    }, [updateEdges]);

    return (
      <div className={cn("relative min-w-0", className)}>
        <div
          aria-label={ariaLabel}
          className={cn("overflow-x-auto", viewportClassName)}
          onKeyDown={(event) => {
            if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
            event.preventDefault();
            const viewport = viewportRef.current;
            if (!viewport) return;
            const distance = Math.max(48, Math.round(viewport.clientWidth * 0.2));
            viewport.scrollLeft += event.key === "ArrowRight" ? distance : -distance;
            updateEdges();
          }}
          onScroll={updateEdges}
          ref={viewportRef}
          role={ariaLabel ? "region" : undefined}
          tabIndex={0}
        >
          {children}
        </div>
        {edges.left ? (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-1 left-0 z-10 flex w-6 items-center justify-start bg-gradient-to-r from-[var(--sh-surface-elevated)]/90 to-transparent pl-0.5 text-[var(--sh-ink-muted)]"
            data-testid={hintTestId ? `${hintTestId}-previous` : undefined}
          >
            <ChevronLeft className="size-4" />
          </span>
        ) : null}
        {edges.right ? (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-1 right-0 z-10 flex w-6 items-center justify-end bg-gradient-to-l from-[var(--sh-surface-elevated)]/90 to-transparent pr-0.5 text-[var(--sh-ink-muted)]"
            data-testid={hintTestId}
          >
            <ChevronRight className="size-4" />
          </span>
        ) : null}
      </div>
    );
  },
);
