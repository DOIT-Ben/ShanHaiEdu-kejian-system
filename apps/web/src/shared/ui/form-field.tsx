import { useId, type ReactNode } from "react";
import { Label } from "./label";
import { cn } from "@/shared/lib/cn";

/**
 * 表单字段布局：Label + 控件 + 描述 + 字段级错误（贴近字段展示）。
 * 具体校验由 React Hook Form + Zod 提供。
 */
export function FormField({
  label,
  required,
  description,
  error,
  children,
  htmlFor,
  className,
}: {
  label: ReactNode;
  required?: boolean;
  description?: ReactNode;
  error?: string;
  htmlFor?: string;
  children: ReactNode | ((props: { id: string; describedBy?: string }) => ReactNode);
  className?: string;
}) {
  const autoId = useId();
  const id = htmlFor ?? autoId;
  const errorId = `${id}-error`;
  const descId = `${id}-desc`;
  const describedBy = error ? errorId : description ? descId : undefined;

  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id}>
        {label}
        {required ? (
          <span className="ml-0.5 text-danger" aria-hidden>
            *
          </span>
        ) : null}
      </Label>
      {typeof children === "function" ? children({ id, describedBy }) : children}
      {description && !error ? (
        <p id={descId} className="text-xs text-ink-muted">
          {description}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
