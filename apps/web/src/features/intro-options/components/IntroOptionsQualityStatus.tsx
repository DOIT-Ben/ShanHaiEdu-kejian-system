import { FileCheck2, ShieldCheck } from "lucide-react";
import { Button } from "@/shared/ui/Button";

type IntroOptionsQualityStatusProps = {
  disabled: boolean;
  failed: boolean;
  onRun: () => void;
  passed: boolean;
  pending: boolean;
  submittedApproved: boolean;
};

export function IntroOptionsQualityStatus({
  disabled,
  failed,
  onRun,
  passed,
  pending,
  submittedApproved,
}: IntroOptionsQualityStatusProps) {
  return (
    <section className="flex flex-wrap items-center gap-3 border-t border-[var(--sh-line-subtle)] pt-5">
      <Button disabled={disabled} onClick={onRun} variant="secondary">
        <ShieldCheck aria-hidden="true" />
        {pending ? "正在检查" : passed ? "质量检查已通过" : "运行质量检查"}
      </Button>
      <p
        className={`flex items-center gap-2 text-sm ${
          failed ? "text-[var(--sh-danger)]" : "text-[var(--sh-ink-muted)]"
        }`}
        role="status"
      >
        <FileCheck2 aria-hidden="true" className="size-4" />
        {submittedApproved
          ? "当前三类九套已经批准"
          : passed
            ? "检查通过，可以批准当前版本"
            : failed
              ? "检查未通过，请修改后重新提交"
              : pending
                ? "正在检查当前提交版本"
                : "提交后运行质量检查"}
      </p>
    </section>
  );
}
