import type { IntroOption } from "@/features/intro-options/model";

export type IntroOptionsDraft = {
  adopted?: boolean;
  adoptedKey?: string;
  adoptedRevision?: number;
  customConceptByKey: Record<string, string>;
  customConceptByRevision: Record<string, Record<string, string>>;
  customOptionByRevision: Record<string, Record<string, IntroOption>>;
  previewKey: string;
  previewRevision: number;
  revisions: Record<string, number>;
  selectedKey?: string;
};

function asRecord(value: unknown) {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function asRevisionRecord(value: unknown) {
  const result: Record<string, number> = {};
  for (const [key, revision] of Object.entries(asRecord(value))) {
    if (typeof revision === "number" && Number.isFinite(revision) && revision >= 0) {
      result[key] = revision;
    }
  }
  return result;
}

function isRevision(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function asStringRecord(value: unknown) {
  const result: Record<string, string> = {};
  for (const [key, item] of Object.entries(asRecord(value))) {
    if (typeof item === "string") result[key] = item;
  }
  return result;
}

function asNestedStringRecord(value: unknown) {
  const result: Record<string, Record<string, string>> = {};
  for (const [key, item] of Object.entries(asRecord(value))) {
    result[key] = asStringRecord(item);
  }
  return result;
}

function asIntroOption(value: unknown): IntroOption | undefined {
  const item = asRecord(value);
  const category = item.category;
  const mustNotPreteach = item.mustNotPreteach;
  if (
    typeof item.key !== "string" ||
    (category !== "science" && category !== "application" && category !== "story") ||
    typeof item.title !== "string" ||
    typeof item.score !== "number" ||
    !Number.isFinite(item.score) ||
    typeof item.concept !== "string" ||
    typeof item.hook !== "string" ||
    typeof item.medium !== "string" ||
    typeof item.duration !== "number" ||
    !Number.isFinite(item.duration) ||
    typeof item.courseAnchor !== "string" ||
    typeof item.firstQuestion !== "string" ||
    typeof item.handoff !== "string" ||
    !Array.isArray(mustNotPreteach) ||
    !mustNotPreteach.every((entry) => typeof entry === "string") ||
    typeof item.reason !== "string"
  ) {
    return undefined;
  }
  return {
    category,
    concept: item.concept,
    courseAnchor: item.courseAnchor,
    duration: item.duration,
    firstQuestion: item.firstQuestion,
    handoff: item.handoff,
    hook: item.hook,
    key: item.key,
    medium: item.medium,
    mustNotPreteach,
    reason: item.reason,
    score: item.score,
    title: item.title,
  };
}

function asNestedIntroOptionRecord(value: unknown) {
  const result: Record<string, Record<string, IntroOption>> = {};
  for (const [key, revisions] of Object.entries(asRecord(value))) {
    const parsedRevisions: Record<string, IntroOption> = {};
    for (const [revision, candidate] of Object.entries(asRecord(revisions))) {
      const option = asIntroOption(candidate);
      if (option?.key === key) parsedRevisions[revision] = option;
    }
    result[key] = parsedRevisions;
  }
  return result;
}

export function readIntroOptionsDraft(value: unknown, fallbackKey: string): IntroOptionsDraft {
  const stored = asRecord(value);
  const legacySelectedKey = typeof stored.selectedKey === "string" ? stored.selectedKey : undefined;
  const previewKey =
    typeof stored.previewKey === "string" ? stored.previewKey : (legacySelectedKey ?? fallbackKey);
  const revisions = asRevisionRecord(stored.revisions);
  const customConceptByKey = asStringRecord(stored.customConceptByKey);
  const customConceptByRevision = asNestedStringRecord(stored.customConceptByRevision);
  const customOptionByRevision = asNestedIntroOptionRecord(stored.customOptionByRevision);
  for (const [optionKey, concept] of Object.entries(customConceptByKey)) {
    const revisionKey = String(revisions[optionKey] ?? 0);
    customConceptByRevision[optionKey] = {
      ...customConceptByRevision[optionKey],
      [revisionKey]: customConceptByRevision[optionKey]?.[revisionKey] ?? concept,
    };
  }
  const adoptedKey =
    typeof stored.adoptedKey === "string"
      ? stored.adoptedKey
      : stored.adopted === true
        ? legacySelectedKey
        : undefined;
  const adoptedRevision = isRevision(stored.adoptedRevision)
    ? stored.adoptedRevision
    : adoptedKey
      ? (revisions[adoptedKey] ?? 0)
      : undefined;

  return {
    adopted: stored.adopted === true,
    adoptedKey,
    adoptedRevision,
    customConceptByKey,
    customConceptByRevision,
    customOptionByRevision,
    previewKey,
    previewRevision: isRevision(stored.previewRevision)
      ? stored.previewRevision
      : (revisions[previewKey] ?? 0),
    revisions,
    selectedKey: legacySelectedKey,
  };
}

export function getIntroOptionRevision(draft: IntroOptionsDraft, optionKey: string) {
  return draft.revisions[optionKey] ?? 0;
}

export function getPreviewedIntroOptionRevision(draft: IntroOptionsDraft) {
  return draft.previewRevision;
}

export function isPreviewAdopted(draft: IntroOptionsDraft) {
  return draft.previewKey === draft.adoptedKey && draft.previewRevision === draft.adoptedRevision;
}

function withLegacyFields(draft: IntroOptionsDraft): IntroOptionsDraft {
  return {
    ...draft,
    adopted: draft.adoptedKey !== undefined,
    selectedKey: draft.adoptedKey ?? draft.previewKey,
  };
}

export function previewIntroOption(draft: IntroOptionsDraft, previewKey: string) {
  return withLegacyFields({
    ...draft,
    previewKey,
    previewRevision: getIntroOptionRevision(draft, previewKey),
  });
}

export function returnToAdoptedIntroOption(draft: IntroOptionsDraft) {
  if (!draft.adoptedKey || draft.adoptedRevision === undefined) return draft;
  return withLegacyFields({
    ...draft,
    previewKey: draft.adoptedKey,
    previewRevision: draft.adoptedRevision,
  });
}

export function adoptPreviewedIntroOption(draft: IntroOptionsDraft) {
  return withLegacyFields({
    ...draft,
    adoptedKey: draft.previewKey,
    adoptedRevision: draft.previewRevision,
  });
}

export function regeneratePreviewedIntroOption(
  draft: IntroOptionsDraft,
  option: IntroOption,
  requirements: string,
) {
  const compactRequirements = requirements.trim().replace(/\s+/g, " ");
  const excerpt = compactRequirements.slice(0, 64);
  const suffix = compactRequirements.length > excerpt.length ? "…" : "";
  const requirementLabel = `${excerpt}${suffix}`.replace(/[，。！？；：,.!?;:]+$/u, "");
  const revision = getIntroOptionRevision(draft, option.key) + 1;
  const conciseNarration = /(减少|少用|精简|缩短|不要).{0,4}(旁白|讲解)|无旁白/u.test(
    compactRequirements,
  );
  const observationFirst = /(观察|互动|参与|提问|讨论)/u.test(compactRequirements);
  const regeneratedOption: IntroOption = requirementLabel
    ? {
        ...option,
        concept: `${option.concept} 新版本重点强化“${requirementLabel}”。`,
        courseAnchor: `${option.courseAnchor} 教师重点围绕“${requirementLabel}”组织观察和比较。`,
        duration: conciseNarration ? Math.max(25, option.duration - 10) : option.duration,
        firstQuestion: observationFirst
          ? `先说说你观察到了什么，再想：${option.firstQuestion}`
          : `结合新的画面线索想一想：${option.firstQuestion}`,
        handoff: conciseNarration
          ? `${option.handoff} 画面停住，不再补充旁白，把判断留给学生。`
          : `${option.handoff} 教师围绕“${requirementLabel}”接回课堂。`,
        hook: conciseNarration
          ? observationFirst
            ? `先请学生说出观察，再直接提问：${option.hook}`
            : `先给学生看画面，再直接提问：${option.hook}`
          : observationFirst
            ? `先请学生说出观察，再追问：${option.hook}`
            : `${option.hook} 开场将重点体现“${requirementLabel}”。`,
        medium: conciseNarration ? "图片 + 提问" : option.medium,
        reason: `已按“${requirementLabel}”调整开场、提问与课堂回接，原教学目标和知识边界保持不变。`,
      }
    : option;
  const concept = regeneratedOption.concept;
  return withLegacyFields({
    ...draft,
    customConceptByKey: {
      ...draft.customConceptByKey,
      [option.key]: concept,
    },
    customConceptByRevision: {
      ...draft.customConceptByRevision,
      [option.key]: {
        ...draft.customConceptByRevision[option.key],
        [String(revision)]: concept,
      },
    },
    customOptionByRevision: {
      ...draft.customOptionByRevision,
      [option.key]: {
        ...draft.customOptionByRevision[option.key],
        [String(revision)]: regeneratedOption,
      },
    },
    previewRevision: revision,
    revisions: { ...draft.revisions, [option.key]: revision },
  });
}

export function resolveIntroOption(
  option: IntroOption,
  draft: IntroOptionsDraft,
  revision = option.key === draft.previewKey
    ? draft.previewRevision
    : getIntroOptionRevision(draft, option.key),
): IntroOption {
  const regeneratedOption = draft.customOptionByRevision[option.key]?.[String(revision)];
  if (regeneratedOption) return regeneratedOption;
  return {
    ...option,
    concept:
      draft.customConceptByRevision[option.key]?.[String(revision)] ??
      (revision === getIntroOptionRevision(draft, option.key)
        ? draft.customConceptByKey[option.key]
        : undefined) ??
      option.concept,
  };
}
