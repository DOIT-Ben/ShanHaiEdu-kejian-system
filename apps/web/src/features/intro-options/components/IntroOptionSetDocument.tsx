import { Check, Clock3 } from "lucide-react";
import type { IntroOptionDto } from "@/features/intro-options/api/introOptionsApi";
import {
  readIntroOptionSet,
  updateIntroOptionField,
  type EditableIntroOptionField,
} from "@/features/intro-options/artifactContent";
import { Button } from "@/shared/ui/Button";

const categories = [
  { key: "science", label: "科普导入" },
  { key: "application", label: "应用导入" },
  { key: "story", label: "故事导入" },
] as const;

const mediumLabels: Record<IntroOptionDto["suggested_medium"], string> = {
  image: "图片",
  mixed: "组合媒介",
  performance: "课堂表演",
  physical_object: "实物",
  question: "直接提问",
  video: "短视频",
};

type IntroOptionSetDocumentProps = {
  canSelect?: boolean;
  content: Record<string, unknown>;
  editable?: boolean;
  onChange?: (content: Record<string, unknown>) => void;
  onSelect?: (optionKey: string) => void;
  selectedOptionKey?: string;
  selectingOptionKey?: string;
};

export function IntroOptionSetDocument({
  canSelect = false,
  content,
  editable = false,
  onChange,
  onSelect,
  selectedOptionKey,
  selectingOptionKey,
}: IntroOptionSetDocumentProps) {
  const optionSet = readIntroOptionSet(content);
  if (!optionSet) {
    return (
      <p className="text-sm text-[var(--sh-danger)]" role="alert">
        当前版本不是完整的三类九套方案，暂时不能编辑或采用。
      </p>
    );
  }

  const changeField = (optionKey: string, field: EditableIntroOptionField, value: string) =>
    onChange?.(updateIntroOptionField(content, optionKey, field, value));

  return (
    <div className="divide-y divide-[var(--sh-line-default)]">
      {categories.map((category) => {
        const options = optionSet.options.filter(
          (option) => option.primary_tendency === category.key,
        );
        return (
          <section className="py-5 first:pt-0 last:pb-0" key={category.key}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 className="font-semibold text-[var(--sh-ink-strong)]">{category.label}</h3>
              <span className="text-xs text-[var(--sh-ink-faint)]">{options.length} 套方案</span>
            </div>
            <div className="divide-y divide-[var(--sh-line-subtle)] md:grid md:grid-cols-3 md:divide-x md:divide-y-0">
              {options.map((option) => (
                <article
                  className="min-w-0 py-4 first:pt-0 last:pb-0 md:px-4 md:py-0 md:first:pl-0 md:last:pr-0"
                  key={option.option_key}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-[var(--sh-ink-faint)]">
                        推荐度 {option.recommendation_score}
                      </p>
                      <h4 className="mt-1 font-semibold text-[var(--sh-ink-strong)]">
                        {option.title}
                      </h4>
                    </div>
                    {selectedOptionKey === option.option_key ? (
                      <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-[var(--sh-success)]">
                        <Check aria-hidden="true" className="size-4" />
                        已采用
                      </span>
                    ) : null}
                  </div>

                  <p className="mt-3 flex items-center gap-2 text-xs text-[var(--sh-ink-muted)]">
                    <Clock3 aria-hidden="true" className="size-3.5" />
                    {mediumLabels[option.suggested_medium]} · {option.duration_seconds} 秒
                  </p>

                  {editable ? (
                    <div className="mt-4 space-y-4">
                      <label className="block text-xs font-medium text-[var(--sh-ink-muted)]">
                        方案正文
                        <textarea
                          className="mt-1 min-h-28 w-full resize-y rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3 py-2 text-sm leading-6 text-[var(--sh-ink-default)]"
                          onChange={(event) =>
                            changeField(option.option_key, "creative_concept", event.target.value)
                          }
                          value={option.creative_concept}
                        />
                      </label>
                      <label className="block text-xs font-medium text-[var(--sh-ink-muted)]">
                        推荐说明
                        <textarea
                          className="mt-1 min-h-24 w-full resize-y rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3 py-2 text-sm leading-6 text-[var(--sh-ink-default)]"
                          onChange={(event) =>
                            changeField(option.option_key, "fit_reason", event.target.value)
                          }
                          value={option.fit_reason}
                        />
                      </label>
                    </div>
                  ) : (
                    <>
                      <p className="mt-3 text-sm leading-6 text-[var(--sh-ink-default)]">
                        {option.creative_concept}
                      </p>
                      <dl className="mt-4 space-y-3 text-sm leading-6">
                        <div>
                          <dt className="text-xs font-medium text-[var(--sh-ink-faint)]">
                            开场钩子
                          </dt>
                          <dd className="text-[var(--sh-ink-muted)]">{option.hook}</dd>
                        </div>
                        <div>
                          <dt className="text-xs font-medium text-[var(--sh-ink-faint)]">
                            课堂回接
                          </dt>
                          <dd className="text-[var(--sh-ink-muted)]">{option.course_anchor}</dd>
                        </div>
                        <div>
                          <dt className="text-xs font-medium text-[var(--sh-ink-faint)]">
                            首个问题
                          </dt>
                          <dd className="text-[var(--sh-ink-muted)]">
                            {option.classroom_first_question}
                          </dd>
                        </div>
                      </dl>
                      <p className="mt-4 border-t border-[var(--sh-line-subtle)] pt-3 text-xs leading-5 text-[var(--sh-ink-muted)]">
                        {option.recommendation_reason}
                      </p>
                    </>
                  )}

                  {canSelect && onSelect ? (
                    <Button
                      className="mt-4 w-full"
                      disabled={Boolean(selectingOptionKey)}
                      onClick={() => onSelect(option.option_key)}
                      variant={selectedOptionKey === option.option_key ? "secondary" : "primary"}
                    >
                      <Check aria-hidden="true" />
                      {selectedOptionKey === option.option_key
                        ? "已采用此方案"
                        : selectingOptionKey === option.option_key
                          ? "正在采用"
                          : "采用本方案"}
                    </Button>
                  ) : null}
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
