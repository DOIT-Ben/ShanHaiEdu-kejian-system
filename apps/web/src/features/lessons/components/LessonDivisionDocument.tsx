type DivisionContent = Record<string, unknown>;
type LessonUnit = Record<string, unknown>;

const lessonTypeLabels: Record<string, string> = {
  activity: "活动课",
  new_learning: "新授课",
  practice: "练习课",
  review: "整理复习课",
};

const textFields = [
  ["core_learning_outcome", "核心学习结果"],
  ["material_scope", "对应教材范围"],
  ["prior_learning", "前置基础"],
  ["content_boundary", "本课讲授边界"],
  ["teaching_focus", "教学重点"],
  ["learning_difficulty", "学习难点"],
  ["division_reason", "划分理由"],
  ["following_connection", "后续衔接"],
] as const;

function recordValue(value: unknown): DivisionContent | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as DivisionContent)
    : undefined;
}

function lessonUnits(content: DivisionContent): LessonUnit[] {
  return Array.isArray(content.lesson_units)
    ? content.lesson_units.flatMap((value) => {
        const unit = recordValue(value);
        return unit ? [unit] : [];
      })
    : [];
}

export function lessonDivisionContentReady(content: DivisionContent | undefined) {
  if (!content) return false;
  const units = lessonUnits(content);
  return (
    units.length > 0 &&
    content.lesson_count === units.length &&
    units.every((unit) => typeof unit.title === "string" && unit.title.trim().length > 0)
  );
}

function stringList(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function textValue(value: unknown) {
  return typeof value === "string" ? value : typeof value === "number" ? String(value) : "";
}

export function LessonDivisionDocument({ content }: { content: DivisionContent }) {
  if (!lessonDivisionContentReady(content)) {
    return (
      <p className="text-sm text-[var(--sh-danger)]" role="alert">
        当前课时划分正文不完整，编辑、质量检查和批准已停用。
      </p>
    );
  }
  return (
    <div className="space-y-4">
      {lessonUnits(content).map((unit, index) => (
        <article
          className="border-l-2 border-[var(--sh-brand-300)] pl-4"
          key={textValue(unit.lesson_unit_key) || `lesson-${String(index + 1)}`}
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="font-semibold text-[var(--sh-ink-strong)]">
              第 {index + 1} 课时 · {textValue(unit.title)}
            </h3>
            <span className="text-xs text-[var(--sh-ink-faint)]">
              {lessonTypeLabels[textValue(unit.lesson_type)] ?? textValue(unit.lesson_type)} ·{" "}
              {textValue(unit.duration_minutes)} 分钟
            </span>
          </div>
          <dl className="mt-3 space-y-2 text-sm leading-6">
            {textFields.map(([key, label]) =>
              typeof unit[key] === "string" && unit[key] ? (
                <div key={key}>
                  <dt className="font-medium text-[var(--sh-ink-muted)]">{label}</dt>
                  <dd className="text-[var(--sh-ink-default)]">{unit[key]}</dd>
                </div>
              ) : null,
            )}
            {stringList(unit.must_not_preteach).length ? (
              <div>
                <dt className="font-medium text-[var(--sh-ink-muted)]">不得提前讲授</dt>
                <dd className="text-[var(--sh-ink-default)]">
                  {stringList(unit.must_not_preteach).join("、")}
                </dd>
              </div>
            ) : null}
          </dl>
        </article>
      ))}
    </div>
  );
}

export function LessonDivisionDraftEditor({
  content,
  onChange,
}: {
  content: DivisionContent;
  onChange: (content: DivisionContent) => void;
}) {
  if (!lessonDivisionContentReady(content)) return <LessonDivisionDocument content={content} />;
  const units = lessonUnits(content);
  const updateUnit = (index: number, update: Partial<LessonUnit>) => {
    onChange({
      ...content,
      lesson_units: units.map((unit, unitIndex) =>
        unitIndex === index ? { ...unit, ...update } : unit,
      ),
    });
  };
  return (
    <div className="space-y-6">
      {units.map((unit, index) => (
        <section
          className="border-b border-[var(--sh-line-subtle)] pb-6 last:border-0 last:pb-0"
          key={textValue(unit.lesson_unit_key) || `lesson-${String(index + 1)}`}
        >
          <h3 className="font-semibold text-[var(--sh-ink-strong)]">第 {index + 1} 课时</h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-xs font-medium text-[var(--sh-ink-muted)]">
              课题名称
              <input
                className="mt-1 h-10 w-full rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] px-3 text-sm"
                onChange={(event) => updateUnit(index, { title: event.target.value })}
                value={textValue(unit.title)}
              />
            </label>
            <label className="text-xs font-medium text-[var(--sh-ink-muted)]">
              课型
              <select
                className="mt-1 h-10 w-full rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] px-3 text-sm"
                onChange={(event) => updateUnit(index, { lesson_type: event.target.value })}
                value={textValue(unit.lesson_type)}
              >
                {Object.entries(lessonTypeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="mt-3 space-y-3">
            {textFields.map(([key, label]) => (
              <label className="block text-xs font-medium text-[var(--sh-ink-muted)]" key={key}>
                {label}
                <textarea
                  className="mt-1 min-h-20 w-full resize-y rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] px-3 py-2 text-sm leading-6"
                  onChange={(event) => updateUnit(index, { [key]: event.target.value })}
                  value={textValue(unit[key])}
                />
              </label>
            ))}
            <label className="block text-xs font-medium text-[var(--sh-ink-muted)]">
              不得提前讲授（使用顿号分隔）
              <input
                className="mt-1 h-10 w-full rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] px-3 text-sm"
                onChange={(event) =>
                  updateUnit(index, {
                    must_not_preteach: event.target.value
                      .split("、")
                      .map((item) => item.trim())
                      .filter(Boolean),
                  })
                }
                value={stringList(unit.must_not_preteach).join("、")}
              />
            </label>
          </div>
        </section>
      ))}
    </div>
  );
}
