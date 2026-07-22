/**
 * Deterministic API adapter used by local mock mode.
 *
 * Feature code talks to this boundary instead of importing the storage-backed
 * runtime directly. The adapter keeps browser mocks and MSW handlers on the
 * same state so mock mode exercises the same API-facing contracts as runtime.
 */
export {
  addMockTextbookFile,
  createMockEntityId,
  createMockProject,
  createMockSaveConflict,
  createMockTask,
  getMockDraft,
  getMockNodeState,
  getMockProject,
  getMockRuntimeState,
  listMockSaveConflicts,
  listMockTasks,
  listMockTextbookFiles,
  mockRuntime,
  resetMockRuntime,
  resolveMockSaveConflict,
  saveMockDraft,
  subscribe,
  updateMockNodeState,
  updateMockProject,
  updateMockTask,
  updateMockTextbookFile,
  useMockRuntime,
  MOCK_RUNTIME_STORAGE_KEY,
} from "@/shared/api/mocks/runtime";

export type {
  CreateMockProjectInput,
  MockDraft,
  MockDraftOptions,
  MockNodeState,
  MockProject,
  MockRole,
  MockRuntimeState,
  MockRuntimeStore,
  MockRuntimeStoreOptions,
  MockSaveConflict,
  MockSession,
  MockTask,
  MockTextbookFile,
  MockTextbookFileInput,
} from "@/shared/api/mocks/runtime";
