import { FileWarning } from "lucide-react";
import { EmptyState } from "@/shared/ui";

/** 产物内容不符合 Schema 时的兜底展示（不允许页面崩溃）。 */
export function InvalidContent({ nodeTitle }: { nodeTitle?: string }) {
  return (
    <EmptyState
      icon={<FileWarning className="size-8" aria-hidden />}
      title="内容格式异常"
      description={`${nodeTitle ?? "该步骤"}的产物内容无法解析，请重新生成或联系管理员。`}
    />
  );
}
