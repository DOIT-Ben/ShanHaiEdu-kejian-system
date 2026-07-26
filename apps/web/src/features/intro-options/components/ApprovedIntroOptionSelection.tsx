import type { IntroOptionSetPublicDto } from "@/features/intro-options/api/introOptionsApi";
import { IntroOptionSetDocument } from "@/features/intro-options/components/IntroOptionSetDocument";

type ApprovedIntroOptionSelectionProps = {
  canSelect: boolean;
  loading: boolean;
  onSelect: (optionKey: string) => void;
  optionSet?: IntroOptionSetPublicDto;
  selectedOptionKey?: string;
  selectingOptionKey?: string;
};

export function ApprovedIntroOptionSelection({
  canSelect,
  loading,
  onSelect,
  optionSet,
  selectedOptionKey,
  selectingOptionKey,
}: ApprovedIntroOptionSelectionProps) {
  return (
    <section
      className="border-t border-[var(--sh-line-subtle)] pt-5"
      aria-labelledby="intro-select-title"
    >
      <h2 className="font-semibold text-[var(--sh-ink-strong)]" id="intro-select-title">
        采用课堂导入方案
      </h2>
      <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
        只可从当前批准版本中采用一套，刷新后仍会恢复相同选择。
      </p>
      {loading ? (
        <p className="mt-4 text-sm text-[var(--sh-ink-muted)]" role="status">
          正在读取批准版本
        </p>
      ) : optionSet ? (
        <div className="mt-4">
          <IntroOptionSetDocument
            canSelect={canSelect}
            content={optionSet}
            onSelect={onSelect}
            selectedOptionKey={selectedOptionKey}
            selectingOptionKey={selectingOptionKey}
          />
        </div>
      ) : (
        <p className="mt-4 text-sm text-[var(--sh-danger)]" role="alert">
          批准版本暂时无法读取，请刷新后重试。
        </p>
      )}
    </section>
  );
}
