import type { WorkflowStatus } from "@/entities/workflow/model";

export type MockRole = "teacher" | "admin";
export type MockAutomationMode = "manual" | "assisted" | "automatic";

export type MockProject = {
  id: string;
  title: string;
  subject: "primary_math";
  grade: string | null;
  textbook_edition: string | null;
  knowledge_point: string;
  status: "draft" | "active" | "archived";
  automation_mode: MockAutomationMode;
  created_at: string;
  updated_at: string;
};

export type MockTextbookFile = {
  id: string;
  project_id: string;
  name: string;
  size: number;
  type: string;
  last_modified: number | null;
  status: "uploaded" | "processing" | "ready" | "failed";
  created_at: string;
};

export type MockNodeState = {
  id: string;
  project_id: string;
  lesson_id: string | null;
  node_key: string;
  title: string;
  status: WorkflowStatus;
  revision: number;
  updated_at: string;
  stale_reason: { summary: string } | null;
};

export type MockTask = {
  id: string;
  project_id: string | null;
  node_run_id: string | null;
  title: string;
  detail: string;
  stage: string;
  status: WorkflowStatus;
  progress: number;
  retry_count: number;
  updated_at: string;
};

export type MockSaveConflict = {
  id: string;
  project_id: string;
  result_id: string;
  slot_key: string;
  current_version: string;
  requested_version: string;
  status: "open" | "replaced" | "kept";
  created_at: string;
  resolved_at: string | null;
};

export type MockSession = {
  id: string;
  token: string;
  user: { id: string; name: string; email: string; role: MockRole };
  issued_at: string;
  expires_at: string;
};

export type MockDraft<T = unknown> = {
  key: string;
  value: T;
  project_id: string | null;
  lesson_id: string | null;
  node_key: string | null;
  revision: number;
  updated_at: string;
};

export type MockRuntimeState = {
  schemaVersion: 1;
  projects: MockProject[];
  textbookFiles: Record<string, MockTextbookFile[]>;
  nodeStates: Record<string, MockNodeState>;
  tasks: MockTask[];
  saveConflicts: MockSaveConflict[];
  drafts: Record<string, MockDraft>;
  session: MockSession | null;
};

export type MockTextbookFileInput = Pick<MockTextbookFile, "name" | "size" | "type"> & {
  lastModified?: number;
};

export type CreateMockProjectInput = {
  title: string;
  knowledge_point: string;
  grade?: string | null;
  textbook_edition?: string | null;
  automation_mode?: MockAutomationMode;
  textbook_file?: MockTextbookFileInput | null;
};

export type MockDraftOptions = {
  projectId?: string;
  lessonId?: string;
  nodeKey?: string;
};

export type MockRuntimeStoreOptions = {
  storage?: Storage | null;
  storageKey?: string;
  seed?: MockRuntimeState;
  now?: () => string;
  idFactory?: () => string;
};

export type MockRuntimeListener = () => void;
export type MockRuntimeStateUpdater = (state: MockRuntimeState) => MockRuntimeState;

export type MockRuntimeStore = {
  getState: () => MockRuntimeState;
  setState: (updater: MockRuntimeStateUpdater) => MockRuntimeState;
  reset: () => MockRuntimeState;
  subscribe: (listener: MockRuntimeListener) => () => void;
  createProject: (input: CreateMockProjectInput) => MockProject;
  getProject: (projectId: string) => MockProject | undefined;
  updateProject: (
    projectId: string,
    patch: Partial<
      Pick<
        MockProject,
        "title" | "grade" | "textbook_edition" | "knowledge_point" | "status" | "automation_mode"
      >
    >,
  ) => MockProject | undefined;
  addTextbookFile: (projectId: string, input: MockTextbookFileInput) => MockTextbookFile;
  updateTextbookFile: (
    projectId: string,
    fileId: string,
    patch: Partial<Pick<MockTextbookFile, "status">>,
  ) => MockTextbookFile | undefined;
  getNodeState: (
    projectId: string,
    lessonId: string | null,
    nodeKey: string,
  ) => MockNodeState | undefined;
  updateNodeState: (
    projectId: string,
    lessonId: string | null,
    nodeKey: string,
    patch: Partial<Omit<MockNodeState, "id" | "project_id" | "lesson_id" | "node_key">>,
  ) => MockNodeState;
  listTasks: (projectId?: string) => MockTask[];
  createTask: (
    input: Pick<MockTask, "title" | "detail" | "stage" | "status"> &
      Partial<Omit<MockTask, "id" | "title" | "detail" | "stage" | "status" | "updated_at">>,
  ) => MockTask;
  updateTask: (taskId: string, patch: Partial<Omit<MockTask, "id">>) => MockTask | undefined;
  createSaveConflict: (
    input: Omit<MockSaveConflict, "id" | "created_at" | "resolved_at" | "status">,
  ) => MockSaveConflict;
  resolveSaveConflict: (
    conflictId: string,
    status: Extract<MockSaveConflict["status"], "replaced" | "kept">,
  ) => MockSaveConflict | undefined;
  saveDraft: <T>(key: string, value: T, options?: MockDraftOptions) => MockDraft<T>;
  setSession: (session: MockSession | null) => void;
};
