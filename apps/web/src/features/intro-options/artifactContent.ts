import type {
  IntroOptionDto,
  IntroOptionSetDto,
} from "@/features/intro-options/api/introOptionsApi";

export type EditableIntroOptionField = "creative_concept" | "fit_reason";

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isIntroOption(value: unknown): value is IntroOptionDto {
  if (!isRecord(value)) return false;
  const tendency = value.primary_tendency;
  const medium = value.suggested_medium;
  return (
    typeof value.option_key === "string" &&
    typeof value.lesson_unit_key === "string" &&
    typeof value.knowledge_point === "string" &&
    (tendency === "science" || tendency === "application" || tendency === "story") &&
    typeof value.title === "string" &&
    typeof value.creative_concept === "string" &&
    typeof value.hook === "string" &&
    typeof value.viewer_value === "string" &&
    ["video", "image", "physical_object", "question", "performance", "mixed"].includes(
      String(medium),
    ) &&
    typeof value.duration_seconds === "number" &&
    typeof value.course_anchor === "string" &&
    typeof value.classroom_first_question === "string" &&
    typeof value.handoff_moment === "string" &&
    isStringArray(value.must_not_preteach) &&
    typeof value.fit_reason === "string" &&
    isStringArray(value.risks) &&
    typeof value.recommendation_score === "number" &&
    typeof value.recommendation_reason === "string"
  );
}

export function readIntroOptionSet(
  content: Record<string, unknown> | undefined,
): IntroOptionSetDto | undefined {
  if (!content || !Array.isArray(content.options) || content.options.length !== 9) return undefined;
  if (!content.options.every(isIntroOption)) return undefined;
  return content as IntroOptionSetDto;
}

export function updateIntroOptionField(
  content: Record<string, unknown>,
  optionKey: string,
  field: EditableIntroOptionField,
  value: string,
): Record<string, unknown> {
  const optionSet = readIntroOptionSet(content);
  if (!optionSet) return content;
  return {
    ...content,
    options: optionSet.options.map((option) =>
      option.option_key === optionKey ? { ...option, [field]: value } : option,
    ),
  };
}
