import { Check, Clock3 } from "lucide-react";
import type {
  IntroOptionDto,
  IntroOptionVersionDto,
  IntroSelectionDto,
} from "@/features/intro-options/api/introOptionsApi";
import { Button } from "@/shared/ui/Button";

const tendencySections = [
  { key: "science", label: "科普倾向" },
  { key: "application", label: "应用倾向" },
  { key: "story", label: "故事倾向" },
] as const;

const mediumLabels: Record<IntroOptionDto["suggested_medium"], string> = {
  image: "图片",
  mixed: "组合媒介",
  performance: "课堂表演",
  physical_object: "实物",
  question: "问题情境",
  video: "视频",
};

function IntroOptionCard({
  disabled,
  onSelect,
  option,
  selected,
}: {
  disabled: boolean;
  onSelect: () => void;
  option: IntroOptionDto;
  selected: boolean;
}) {
  return (
    <article className="flex min-w-0 flex-col rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4 shadow-[var(--sh-shadow-card)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="break-words font-semibold text-[var(--sh-ink-strong)]">{option.title}</h4>
        </div>
        <span className="shrink-0 rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] px-2 py-1 text-xs font-medium text-[var(--sh-brand-700)]">
          推荐分 {option.recommendation_score}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-[var(--sh-ink-default)]">
        {option.creative_concept}
      </p>
      <dl className="mt-4 grid gap-3 border-t border-[var(--sh-line-subtle)] pt-4 text-sm">
        <div>
          <dt className="font-medium text-[var(--sh-ink-strong)]">开场问题</dt>
          <dd className="mt-1 leading-6 text-[var(--sh-ink-muted)]">{option.hook}</dd>
        </div>
        <div>
          <dt className="font-medium text-[var(--sh-ink-strong)]">课程锚点</dt>
          <dd className="mt-1 leading-6 text-[var(--sh-ink-muted)]">{option.course_anchor}</dd>
        </div>
        <div>
          <dt className="font-medium text-[var(--sh-ink-strong)]">课堂回接</dt>
          <dd className="mt-1 leading-6 text-[var(--sh-ink-muted)]">{option.handoff_moment}</dd>
        </div>
      </dl>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-4">
        <span className="inline-flex items-center gap-1.5 text-xs text-[var(--sh-ink-muted)]">
          <Clock3 aria-hidden="true" className="size-3.5" />
          {mediumLabels[option.suggested_medium]} · {option.duration_seconds} 秒
        </span>
        <Button
          aria-label={`${selected ? "已选方案" : "选用方案"}：${option.title}`}
          disabled={disabled || selected}
          onClick={onSelect}
          size="sm"
          variant={selected ? "secondary" : "primary"}
        >
          <Check aria-hidden="true" />
          {selected ? "当前选择" : "选用此方案"}
        </Button>
      </div>
    </article>
  );
}

export function IntroOptionSet({
  onSelect,
  selection,
  version,
  writeDisabled,
}: {
  onSelect: (option: IntroOptionDto) => void;
  selection?: IntroSelectionDto | null;
  version: IntroOptionVersionDto;
  writeDisabled: boolean;
}) {
  const selectedVersion = selection?.artifact_version_id === version.artifact_version_id;
  return (
    <div className="space-y-6">
      {selection?.active ? (
        <p
          className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-success-soft)] px-3 py-2 text-sm text-[var(--sh-success-strong)]"
          role="status"
        >
          当前选择：{selection.snapshot.title}
        </p>
      ) : null}
      {tendencySections.map((section) => {
        const options = version.option_set.options.filter(
          (option) => option.primary_tendency === section.key,
        );
        if (!options.length) return null;
        return (
          <section aria-labelledby={`intro-tendency-${section.key}`} key={section.key}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3
                className="font-semibold text-[var(--sh-ink-strong)]"
                id={`intro-tendency-${section.key}`}
              >
                {section.label}
              </h3>
              <span className="text-xs text-[var(--sh-ink-muted)]">{options.length} 套</span>
            </div>
            <div className="mt-3 grid gap-3 xl:grid-cols-3">
              {options.map((option) => {
                const selected =
                  selectedVersion && selection.option_key === option.option_key && selection.active;
                return (
                  <IntroOptionCard
                    disabled={writeDisabled || !version.selectable}
                    key={option.option_key}
                    onSelect={() => onSelect(option)}
                    option={option}
                    selected={selected}
                  />
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
