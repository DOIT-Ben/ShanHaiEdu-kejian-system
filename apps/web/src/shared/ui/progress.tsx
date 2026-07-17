import * as ProgressPrimitive from "@radix-ui/react-progress";
import { cn } from "@/shared/lib/cn";

export function Progress({
  value,
  className,
  tone = "running",
  label,
}: {
  value: number;
  className?: string;
  tone?: "running" | "brand" | "success" | "danger";
  label?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const toneClass = {
    running: "bg-running",
    brand: "bg-brand-500",
    success: "bg-success",
    danger: "bg-danger",
  }[tone];
  return (
    <ProgressPrimitive.Root
      value={clamped}
      aria-label={label ?? "进度"}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-canvas", className)}
    >
      <ProgressPrimitive.Indicator
        className={cn("h-full rounded-full transition-[width] duration-300", toneClass)}
        style={{ width: `${clamped}%` }}
      />
    </ProgressPrimitive.Root>
  );
}
