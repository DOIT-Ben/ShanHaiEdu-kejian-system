const lessonPlanSections = [
  ["teaching_content", "一、教学内容"],
  ["material_analysis", "二、教材分析"],
  ["learner_analysis", "三、学情分析"],
  ["design_intent", "四、设计意图"],
  ["teaching_objectives", "五、教学目标"],
  ["key_difficulties_and_strategies", "六、教学重难点及突破策略"],
  ["preparation", "七、教学准备"],
  ["teaching_process", "八、教学过程"],
  ["board_design", "九、板书设计"],
  ["lesson_summary", "十、课堂总结"],
  ["differentiated_homework", "十一、分层作业"],
  ["teaching_reflection", "十二、教学反思"],
] as const;

function recordValue(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function hiddenField(key: string) {
  return key.endsWith("_key") || key.endsWith("_refs") || key.endsWith("_keys");
}

function visibleLines(value: unknown, key = ""): string[] {
  if (hiddenField(key)) return [];
  if (typeof value === "string") {
    const text = value.trim();
    return text && text !== "not_taught" ? [text] : [];
  }
  if (typeof value === "number") {
    return key.includes("minutes") ? [`${String(value)} 分钟`] : [];
  }
  if (Array.isArray(value)) return value.flatMap((item) => visibleLines(item, key));
  const record = recordValue(value);
  return record
    ? Object.entries(record).flatMap(([childKey, child]) => visibleLines(child, childKey))
    : [];
}

export function lessonPlanContentReady(content: Record<string, unknown> | undefined) {
  return Boolean(
    content &&
    lessonPlanSections.every(([key]) => {
      const value = content[key];
      return Array.isArray(value) || recordValue(value) !== undefined;
    }),
  );
}

export function LessonPlanDocument({ content }: { content: Record<string, unknown> }) {
  if (!lessonPlanContentReady(content)) {
    return (
      <p className="text-sm text-[var(--sh-danger)]" role="alert">
        当前教案正文不完整，编辑、质量校验和批准已停用。
      </p>
    );
  }
  return (
    <div className="divide-y divide-[var(--sh-line-subtle)]">
      {lessonPlanSections.map(([key, label]) => {
        const lines = visibleLines(content[key], key);
        return (
          <section className="py-5 first:pt-0 last:pb-0" key={key}>
            <h3 className="font-semibold text-[var(--sh-ink-strong)]">{label}</h3>
            {lines.length ? (
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--sh-ink-default)]">
                {lines.map((line, index) => (
                  <li className="flex gap-2" key={`${key}-${String(index)}`}>
                    <span className="mt-2.5 size-1.5 shrink-0 rounded-full bg-[var(--sh-brand-500)]" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-[var(--sh-ink-muted)]">本部分暂无可展示正文。</p>
            )}
          </section>
        );
      })}
    </div>
  );
}

export function LessonPlanDraftEditor({
  content,
  onChange,
}: {
  content: Record<string, unknown>;
  onChange: (content: Record<string, unknown>) => void;
}) {
  const teachingContent = recordValue(content.teaching_content);
  const topic = teachingContent?.lesson_topic;
  if (!teachingContent || typeof topic !== "string" || !lessonPlanContentReady(content)) {
    return <LessonPlanDocument content={content} />;
  }
  return (
    <div>
      <label className="block text-sm font-medium text-[var(--sh-ink-default)]">
        课题
        <input
          className="mt-2 min-h-11 w-full rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3"
          onChange={(event) =>
            onChange({
              ...content,
              teaching_content: { ...teachingContent, lesson_topic: event.target.value },
            })
          }
          value={topic}
        />
      </label>
      <div className="mt-5 border-t border-[var(--sh-line-subtle)] pt-5">
        <LessonPlanDocument content={content} />
      </div>
    </div>
  );
}
