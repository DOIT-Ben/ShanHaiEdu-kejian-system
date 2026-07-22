import type { UploadSessionDto } from "@/features/materials/api/materialsApi";

/**
 * A browser refresh cannot keep a File object, but it can keep the intent and
 * the server identifiers that make the create/upload/confirm sequence safe to
 * resume. The selected file is therefore represented by its immutable
 * metadata (and, once computed, its digest); the user only needs to select the
 * same file again before a pending upload can continue.
 */
export const RUNTIME_NEW_PROJECT_RECOVERY_KEY = "shanhaiedu.runtime.new-project.v1";

export type RuntimeNewProjectForm = {
  executionMode: "guided" | "automatic";
  grade: string;
  knowledgePoint: string;
  sourceMode: "textbook" | "anchor";
  textbookEdition: string;
  title: string;
};

export type RuntimeNewProjectFile = {
  name: string;
  size: number;
  lastModified: number;
  type: string;
  sha256?: string;
};

export type RuntimeNewProjectStage = "idle" | "checking" | "creating" | "uploading" | "confirming";

export type RuntimeNewProjectRecovery = {
  version: 1;
  form: RuntimeNewProjectForm;
  file?: RuntimeNewProjectFile;
  fingerprint: string;
  intent: {
    confirm: string;
    project: string;
    upload: string;
  };
  stage: RuntimeNewProjectStage;
  projectId?: string;
  uploadSession?: UploadSessionDto;
  etag?: string;
  jobId?: string;
  errorMessage?: string;
  updatedAt: number;
};

export const defaultRuntimeNewProjectForm: RuntimeNewProjectForm = {
  executionMode: "guided",
  grade: "六年级",
  knowledgePoint: "",
  sourceMode: "textbook",
  textbookEdition: "人教版",
  title: "",
};

function newId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `runtime-${String(Date.now())}-${Math.random().toString(36).slice(2)}`;
}

export function createRuntimeNewProjectRecovery(
  form: RuntimeNewProjectForm = defaultRuntimeNewProjectForm,
): RuntimeNewProjectRecovery {
  return {
    version: 1,
    form,
    fingerprint: "",
    intent: { confirm: newId(), project: newId(), upload: newId() },
    stage: "idle",
    updatedAt: Date.now(),
  };
}

function isForm(value: unknown): value is RuntimeNewProjectForm {
  if (!value || typeof value !== "object") return false;
  const form = value as Partial<RuntimeNewProjectForm>;
  return (
    (form.executionMode === "guided" || form.executionMode === "automatic") &&
    typeof form.grade === "string" &&
    typeof form.knowledgePoint === "string" &&
    (form.sourceMode === "textbook" || form.sourceMode === "anchor") &&
    typeof form.textbookEdition === "string" &&
    typeof form.title === "string"
  );
}

function isFile(value: unknown): value is RuntimeNewProjectFile {
  if (!value || typeof value !== "object") return false;
  const file = value as Partial<RuntimeNewProjectFile>;
  return (
    typeof file.name === "string" &&
    typeof file.size === "number" &&
    Number.isFinite(file.size) &&
    typeof file.lastModified === "number" &&
    Number.isFinite(file.lastModified) &&
    typeof file.type === "string" &&
    (file.sha256 === undefined || typeof file.sha256 === "string")
  );
}

function isUploadSession(value: unknown): value is UploadSessionDto {
  if (!value || typeof value !== "object") return false;
  const session = value as Partial<UploadSessionDto>;
  return (
    typeof session.upload_session_id === "string" &&
    typeof session.material_id === "string" &&
    typeof session.upload_url === "string" &&
    session.method === "PUT" &&
    !!session.required_headers &&
    typeof session.required_headers === "object" &&
    typeof session.expires_at === "string"
  );
}

function isIntent(value: unknown): value is RuntimeNewProjectRecovery["intent"] {
  if (!value || typeof value !== "object") return false;
  const intent = value as Partial<RuntimeNewProjectRecovery["intent"]>;
  return (
    typeof intent.confirm === "string" &&
    typeof intent.project === "string" &&
    typeof intent.upload === "string"
  );
}

function isStage(value: unknown): value is RuntimeNewProjectStage {
  return (
    value === "idle" ||
    value === "checking" ||
    value === "creating" ||
    value === "uploading" ||
    value === "confirming"
  );
}

function isRecovery(value: unknown): value is RuntimeNewProjectRecovery {
  if (!value || typeof value !== "object") return false;
  const recovery = value as Partial<RuntimeNewProjectRecovery>;
  return (
    recovery.version === 1 &&
    isForm(recovery.form) &&
    (recovery.file === undefined || isFile(recovery.file)) &&
    typeof recovery.fingerprint === "string" &&
    isIntent(recovery.intent) &&
    isStage(recovery.stage) &&
    (recovery.uploadSession === undefined || isUploadSession(recovery.uploadSession)) &&
    (recovery.projectId === undefined || typeof recovery.projectId === "string") &&
    (recovery.etag === undefined || typeof recovery.etag === "string") &&
    (recovery.jobId === undefined || typeof recovery.jobId === "string") &&
    (recovery.errorMessage === undefined || typeof recovery.errorMessage === "string") &&
    typeof recovery.updatedAt === "number"
  );
}

export function readRuntimeNewProjectRecovery(): RuntimeNewProjectRecovery | null {
  try {
    const raw = sessionStorage.getItem(RUNTIME_NEW_PROJECT_RECOVERY_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const candidate = parsed as { form?: Record<string, unknown> };
    const migrated =
      candidate.form && candidate.form.sourceMode === undefined
        ? { ...candidate, form: { ...candidate.form, sourceMode: "textbook" } }
        : candidate;
    return isRecovery(migrated) ? migrated : null;
  } catch {
    return null;
  }
}

export function writeRuntimeNewProjectRecovery(recovery: RuntimeNewProjectRecovery) {
  try {
    sessionStorage.setItem(RUNTIME_NEW_PROJECT_RECOVERY_KEY, JSON.stringify(recovery));
  } catch {
    // Private browsing or a full storage quota must not break the upload flow.
  }
}

export function clearRuntimeNewProjectRecovery() {
  try {
    sessionStorage.removeItem(RUNTIME_NEW_PROJECT_RECOVERY_KEY);
  } catch {
    // Ignore unavailable storage; the current form still remains usable.
  }
}

export function fileSnapshot(file: File): RuntimeNewProjectFile {
  return {
    lastModified: file.lastModified,
    name: file.name,
    size: file.size,
    type: file.type || "application/pdf",
  };
}

export function sameFileSnapshot(
  left: RuntimeNewProjectFile | undefined,
  right: RuntimeNewProjectFile | undefined,
) {
  return Boolean(
    left &&
    right &&
    left.name === right.name &&
    left.size === right.size &&
    left.lastModified === right.lastModified &&
    left.type === right.type,
  );
}

/** Stable metadata fingerprint used to decide whether a new intent is needed. */
export function runtimeNewProjectFingerprint(
  form: RuntimeNewProjectForm,
  file: RuntimeNewProjectFile | undefined,
) {
  return JSON.stringify({
    file: file
      ? { lastModified: file.lastModified, name: file.name, size: file.size, type: file.type }
      : null,
    form,
  });
}

export function withNewRuntimeNewProjectIntent(
  form: RuntimeNewProjectForm,
  file: RuntimeNewProjectFile | undefined,
): RuntimeNewProjectRecovery {
  return {
    ...createRuntimeNewProjectRecovery(form),
    file,
    fingerprint: runtimeNewProjectFingerprint(form, file),
  };
}

export function isRuntimeUploadSessionExpired(session: UploadSessionDto, now = Date.now()) {
  const expiresAt = Date.parse(session.expires_at);
  return !Number.isFinite(expiresAt) || expiresAt <= now;
}

/**
 * Keeps the already-created project but rotates the upload and confirmation
 * intents when a signed upload URL has expired. Reusing the old URL would make
 * every refresh retry the same permanently-invalid request.
 */
export function refreshExpiredRuntimeUploadSession(
  recovery: RuntimeNewProjectRecovery,
  now = Date.now(),
): RuntimeNewProjectRecovery {
  if (!recovery.uploadSession || !isRuntimeUploadSessionExpired(recovery.uploadSession, now)) {
    return recovery;
  }
  return {
    ...recovery,
    etag: undefined,
    errorMessage: undefined,
    intent: {
      ...recovery.intent,
      confirm: newId(),
      upload: newId(),
    },
    jobId: undefined,
    stage: "uploading",
    updatedAt: now,
    uploadSession: undefined,
  };
}
