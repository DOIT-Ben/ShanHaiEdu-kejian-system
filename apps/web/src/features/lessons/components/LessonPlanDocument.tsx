type LessonPlanContent = Record<string, unknown>;
type FieldPath = Array<number | string>;

export const lessonPlanSections = [
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

export function lessonPlanSectionId(key: (typeof lessonPlanSections)[number][0]) {
  return `lesson-plan-section-${key}`;
}

export function LessonPlanSectionNavigation() {
  return (
    <nav aria-label="教案十二部分目录">
      <p className="text-xs font-semibold text-[var(--sh-ink-faint)]">教案目录</p>
      <ol className="mt-3 grid grid-cols-2 gap-1 sm:grid-cols-3 xl:grid-cols-1">
        {lessonPlanSections.map(([key, label]) => (
          <li key={key}>
            <a
              className="flex min-h-11 items-center rounded-[var(--sh-radius-control)] border-l-2 border-l-transparent px-2.5 py-2 text-xs leading-5 text-[var(--sh-ink-muted)] transition-colors duration-[var(--sh-duration-fast)] hover:border-l-[var(--sh-brand-400)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)] focus-visible:outline-none focus-visible:shadow-[var(--sh-shadow-focus)] motion-reduce:transition-none"
              href={`#${lessonPlanSectionId(key)}`}
            >
              {label}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

const fieldLabels: Record<string, string> = {
  board_final_content: "板书内容",
  board_layout: "板书布局",
  completion_condition: "完成条件",
  content_boundary: "内容边界",
  criterion: "评价标准",
  current_focus: "本课重点",
  expected_responses: "预期回应",
  homework_answer_guidance: "作业指导",
  homework_criteria: "完成标准",
  homework_level: "作业层次",
  homework_task: "作业任务",
  key_learning_focus: "学习重点",
  lesson_topic: "课题",
  lesson_type: "课型",
  observable_outcome: "可观察目标",
  prior_learning: "已有基础",
  process_design_rationale: "设计理由",
  process_title: "环节名称",
  process_transition: "环节过渡",
  reflection_prompts: "反思提示",
  scaffolds_and_followups: "支持与追问",
  success_criteria: "达成标准",
  teacher_closure: "教师小结",
  teacher_reflection_record: "课后反思记录",
  teaching_scope: "教学范围",
  teaching_value: "教学价值",
};

const nonEditableFields = new Set([
  "assessment_evidence_keys",
  "grade",
  "homework_key",
  "homework_objective_keys",
  "lesson_plan_key",
  "objective_evidence_refs",
  "objective_key",
  "process_objective_keys",
  "process_section_key",
  "reflection_state",
  "source_lesson_unit_key",
  "subject",
  "teaching_evidence_refs",
]);

function recordValue(value: unknown): LessonPlanContent | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as LessonPlanContent)
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

type EditableField = { key: string; path: FieldPath; value: string };

function editableFields(value: unknown, path: FieldPath = [], key = ""): EditableField[] {
  if (hiddenField(key) || nonEditableFields.has(key)) return [];
  if (typeof value === "string") {
    return value === "not_taught" ? [] : [{ key, path, value }];
  }
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => editableFields(item, [...path, index], key));
  }
  const record = recordValue(value);
  return record
    ? Object.entries(record).flatMap(([childKey, child]) =>
        editableFields(child, [...path, childKey], childKey),
      )
    : [];
}

function replaceAtPath(value: unknown, path: FieldPath, replacement: string): unknown {
  if (path.length === 0) return replacement;
  const [head, ...tail] = path;
  if (typeof head === "number" && Array.isArray(value)) {
    const items: unknown[] = value;
    return items.map((item, index) =>
      index === head ? replaceAtPath(item, tail, replacement) : item,
    );
  }
  const record = recordValue(value);
  if (typeof head === "string" && record) {
    return { ...record, [head]: replaceAtPath(record[head], tail, replacement) };
  }
  return value;
}

export function lessonPlanContentReady(content: LessonPlanContent | undefined) {
  return Boolean(
    content &&
    lessonPlanSections.every(([key]) => {
      const value = content[key];
      return Array.isArray(value) || recordValue(value) !== undefined;
    }),
  );
}

export function LessonPlanDocument({ content }: { content: LessonPlanContent }) {
  if (!lessonPlanContentReady(content)) {
    return (
      <p className="text-sm text-[var(--sh-danger)]" role="alert">
        当前教案正文不完整，编辑、质量检查和批准已停用。
      </p>
    );
  }
  return (
    <div className="divide-y divide-[var(--sh-line-subtle)]">
      {lessonPlanSections.map(([key, label]) => {
        const lines = visibleLines(content[key], key);
        const sectionId = lessonPlanSectionId(key);
        return (
          <section
            aria-labelledby={`${sectionId}-title`}
            className="scroll-mt-28 py-6 first:pt-0 last:pb-0"
            id={sectionId}
            key={key}
          >
            <h3 className="font-semibold text-[var(--sh-ink-strong)]" id={`${sectionId}-title`}>
              {label}
            </h3>
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
              <p className="mt-3 text-sm text-[var(--sh-ink-muted)]">本部分暂无正文。</p>
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
  content: LessonPlanContent;
  onChange: (content: LessonPlanContent) => void;
}) {
  if (!lessonPlanContentReady(content)) return <LessonPlanDocument content={content} />;
  return (
    <div className="divide-y divide-[var(--sh-line-subtle)]">
      {lessonPlanSections.map(([sectionKey, sectionLabel]) => {
        const fields = editableFields(content[sectionKey], [sectionKey], sectionKey);
        const sectionId = lessonPlanSectionId(sectionKey);
        return (
          <section
            aria-labelledby={`${sectionId}-title`}
            className="scroll-mt-28 py-6 first:pt-0 last:pb-0"
            id={sectionId}
            key={sectionKey}
          >
            <h3 className="font-semibold text-[var(--sh-ink-strong)]" id={`${sectionId}-title`}>
              {sectionLabel}
            </h3>
            <div className="mt-3 space-y-3">
              {fields.map((field, index) => {
                const label = fieldLabels[field.key] ?? "正文内容";
                return (
                  <label className="block" key={field.path.join(".")}>
                    <span className="text-xs font-medium text-[var(--sh-ink-muted)]">{label}</span>
                    <textarea
                      aria-label={`${sectionLabel} ${label} ${String(index + 1)}`}
                      className="mt-1 min-h-20 w-full resize-y rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-paper)] px-3 py-2 text-sm leading-6 text-[var(--sh-ink-default)] outline-none transition-[border-color,box-shadow] duration-[var(--sh-duration-fast)] focus:border-[var(--sh-brand-500)] focus:shadow-[var(--sh-shadow-focus)] motion-reduce:transition-none"
                      onChange={(event) =>
                        onChange(
                          replaceAtPath(
                            content,
                            field.path,
                            event.target.value,
                          ) as LessonPlanContent,
                        )
                      }
                      value={field.value}
                    />
                  </label>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
