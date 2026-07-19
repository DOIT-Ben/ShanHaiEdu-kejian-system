import type { ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

type WorkbenchPageFrameProps = {
  children: ReactNode;
  className?: string;
  width?: "document" | "narrow" | "standard" | "workspace" | "wide";
};

const widthClasses = {
  document: "max-w-5xl",
  narrow: "max-w-4xl",
  standard: "max-w-6xl",
  workspace: "max-w-[1200px]",
  wide: "max-w-[1440px]",
} as const;

export function WorkbenchPageFrame({
  children,
  className,
  width = "standard",
}: WorkbenchPageFrameProps) {
  return (
    <div
      className={cn(
        "mx-auto min-h-full w-full px-3 py-3 md:px-5 md:py-4",
        widthClasses[width],
        className,
      )}
    >
      {children}
    </div>
  );
}
