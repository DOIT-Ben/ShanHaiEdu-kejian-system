import {
  type MockDraft,
  type MockRuntimeState,
  type MockRuntimeStore,
  mockRuntime,
} from "@/shared/api/mocks/runtime";

export type MockSavedResultType = "image" | "ppt_page" | "video" | "audio" | "document";

export type MockSavedResultPreview = {
  candidate: number;
  generation: number;
  ratio: string;
};

export type MockSavedResult = {
  id: string;
  projectId: string;
  resultId: string;
  type: MockSavedResultType;
  title: string;
  preview?: MockSavedResultPreview;
  slotKey: string;
  slotLabel: string;
  lessonLabel: string;
  replaceMode: "replace" | "append";
  version: number;
  savedAt: string;
};

export type SaveMockResultInput = Omit<MockSavedResult, "id" | "savedAt" | "version">;

function isSavedResultType(value: unknown): value is MockSavedResultType {
  return (
    value === "image" ||
    value === "ppt_page" ||
    value === "video" ||
    value === "audio" ||
    value === "document"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseMockSavedResultPreview(value: unknown): MockSavedResultPreview | null {
  if (!isRecord(value)) return null;
  const { candidate, generation, ratio } = value;
  if (
    typeof candidate !== "number" ||
    !Number.isInteger(candidate) ||
    candidate < 0 ||
    typeof generation !== "number" ||
    !Number.isInteger(generation) ||
    generation < 0 ||
    (ratio !== "1:1" && ratio !== "4:3" && ratio !== "16:9")
  ) {
    return null;
  }
  return { candidate, generation, ratio };
}

const savedResultPrefix = (projectId: string) => `project:${projectId}:saved-result:`;
const currentResultKey = (projectId: string, slotKey: string) =>
  `${savedResultPrefix(projectId)}current:${encodeURIComponent(slotKey)}`;
const resultHistoryKey = (projectId: string, slotKey: string) =>
  `${savedResultPrefix(projectId)}history:${encodeURIComponent(slotKey)}`;

export function mockSavedResultKey(
  input: Pick<SaveMockResultInput, "projectId" | "resultId" | "slotKey">,
) {
  return currentResultKey(input.projectId, input.slotKey);
}

function parseMockSavedResult(value: unknown): MockSavedResult | null {
  if (!value || typeof value !== "object") return null;
  const result = value as Partial<MockSavedResult>;
  if (
    typeof result.id !== "string" ||
    typeof result.projectId !== "string" ||
    typeof result.resultId !== "string" ||
    !isSavedResultType(result.type) ||
    typeof result.title !== "string" ||
    typeof result.slotKey !== "string" ||
    typeof result.slotLabel !== "string" ||
    typeof result.savedAt !== "string"
  ) {
    return null;
  }
  const preview = parseMockSavedResultPreview(result.preview);
  return {
    id: result.id,
    lessonLabel: typeof result.lessonLabel === "string" ? result.lessonLabel : "独立创作",
    projectId: result.projectId,
    ...(preview ? { preview } : {}),
    replaceMode: result.replaceMode === "append" ? "append" : "replace",
    resultId: result.resultId,
    savedAt: result.savedAt,
    slotKey: result.slotKey,
    slotLabel: result.slotLabel,
    title: result.title,
    type: result.type,
    version:
      typeof result.version === "number" && Number.isInteger(result.version) && result.version > 0
        ? result.version
        : 1,
  };
}

function compareResultVersion(left: MockSavedResult, right: MockSavedResult) {
  return left.version - right.version || left.savedAt.localeCompare(right.savedAt);
}

export function listMockSavedResults(state: MockRuntimeState, projectId: string) {
  const currentBySlot = new Map<string, MockSavedResult>();
  for (const [key, draft] of Object.entries(state.drafts)) {
    if (!key.startsWith(savedResultPrefix(projectId))) continue;
    const result = parseMockSavedResult(draft.value);
    if (!result) continue;
    const previous = currentBySlot.get(result.slotKey);
    if (!previous || compareResultVersion(result, previous) > 0) {
      currentBySlot.set(result.slotKey, result);
    }
  }
  return [...currentBySlot.values()].sort((left, right) =>
    right.savedAt.localeCompare(left.savedAt),
  );
}

function parseHistory(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value
    .map(parseMockSavedResult)
    .filter((result): result is MockSavedResult => result !== null);
}

export function listMockSavedResultHistory(
  state: MockRuntimeState,
  projectId: string,
  slotKey: string,
) {
  const current = listMockSavedResults(state, projectId).find(
    (result) => result.slotKey === slotKey,
  );
  const archived = parseHistory(state.drafts[resultHistoryKey(projectId, slotKey)]?.value);
  const versions = current ? [current, ...archived] : archived;
  return versions
    .filter(
      (result, index, items) =>
        items.findIndex((candidate) => candidate.id === result.id) === index,
    )
    .sort((left, right) => compareResultVersion(right, left));
}

function createDraft<T>(
  key: string,
  value: T,
  previous: MockDraft | undefined,
  projectId: string,
  updatedAt: string,
): MockDraft<T> {
  return {
    key,
    lesson_id: previous?.lesson_id ?? null,
    node_key: previous?.node_key ?? null,
    project_id: projectId,
    revision: (previous?.revision ?? 0) + 1,
    updated_at: updatedAt,
    value,
  };
}

function makeSavedResult(
  input: SaveMockResultInput,
  savedAt: string,
  version: number,
): MockSavedResult {
  return {
    ...input,
    id: `${input.resultId}:${input.slotKey}`,
    savedAt,
    version,
  };
}

function invalidateDeliveryPackage(
  drafts: Record<string, MockDraft>,
  projectId: string,
  invalidatedAt: string,
) {
  const key = `project:${projectId}:delivery-package`;
  const previous = drafts[key];
  if (!previous) return;
  const previousValue = previous.value;
  const wasReady =
    previousValue === "ready" ||
    (typeof previousValue === "object" &&
      previousValue !== null &&
      "status" in previousValue &&
      previousValue.status === "ready");
  if (!wasReady) return;
  const details: Record<string, unknown> = isRecord(previousValue) ? previousValue : {};
  drafts[key] = createDraft(
    key,
    {
      ...details,
      invalidatedAt,
      invalidatedReason: "result-version-changed",
      status: "stale",
    },
    previous,
    projectId,
    invalidatedAt,
  );
}

function writeMockResult(
  input: SaveMockResultInput,
  fallbackCurrent: SaveMockResultInput | null,
  store: MockRuntimeStore,
) {
  const existing = listMockSavedResults(store.getState(), input.projectId).find(
    (result) => result.slotKey === input.slotKey,
  );
  if (existing?.resultId === input.resultId) return existing;

  const savedAt = new Date().toISOString();
  let savedResult = makeSavedResult(input, savedAt, 1);
  store.setState((current) => {
    const currentExisting = listMockSavedResults(current, input.projectId).find(
      (result) => result.slotKey === input.slotKey,
    );
    const fallback = fallbackCurrent ? makeSavedResult(fallbackCurrent, savedAt, 1) : null;
    const previousCurrent = currentExisting ?? fallback;
    savedResult = makeSavedResult(input, savedAt, (previousCurrent?.version ?? 0) + 1);

    const drafts: Record<string, MockDraft> = {};
    for (const [key, draft] of Object.entries(current.drafts)) {
      const storedResult = key.startsWith(savedResultPrefix(input.projectId))
        ? parseMockSavedResult(draft.value)
        : null;
      if (storedResult?.slotKey !== input.slotKey) drafts[key] = draft;
    }

    const historyKey = resultHistoryKey(input.projectId, input.slotKey);
    const previousHistoryDraft = current.drafts[historyKey];
    const archived = parseHistory(previousHistoryDraft?.value);
    const nextHistory = previousCurrent
      ? [previousCurrent, ...archived].filter(
          (result, index, items) =>
            items.findIndex((candidate) => candidate.id === result.id) === index,
        )
      : archived;
    if (nextHistory.length > 0) {
      drafts[historyKey] = createDraft(
        historyKey,
        nextHistory,
        previousHistoryDraft,
        input.projectId,
        savedAt,
      );
    }

    const currentKey = currentResultKey(input.projectId, input.slotKey);
    drafts[currentKey] = createDraft(
      currentKey,
      savedResult,
      current.drafts[currentKey],
      input.projectId,
      savedAt,
    );
    invalidateDeliveryPackage(drafts, input.projectId, savedAt);
    return { ...current, drafts };
  });
  return savedResult;
}

export function saveMockResult(input: SaveMockResultInput, store: MockRuntimeStore = mockRuntime) {
  return writeMockResult(input, null, store);
}

export function replaceMockResult(
  input: SaveMockResultInput,
  fallbackCurrent: SaveMockResultInput,
  store: MockRuntimeStore = mockRuntime,
) {
  return writeMockResult(input, fallbackCurrent, store);
}
