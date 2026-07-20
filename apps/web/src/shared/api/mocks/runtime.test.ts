import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createMockProject,
  createMockRuntimeStore,
  createDefaultMockRuntimeState,
  getMockProject,
  mockRuntime,
  resetMockRuntime,
  saveMockDraft,
} from "@/shared/api/mocks/runtime";
import { MockRuntimeStorageError } from "@/shared/api/mocks/runtimeStorage";
import {
  canUseMockAuth,
  createMockSession,
  getMockSession,
  hasMockRole,
  MockAuthError,
  resolveMockSessionSnapshot,
  signIn,
  signOut,
} from "@/shared/auth/mockAuth";

describe("mock runtime persistence", () => {
  beforeEach(() => {
    localStorage.clear();
    resetMockRuntime();
  });

  it("persists a created project, its textbook file, and a draft across store instances", () => {
    const project = createMockProject({
      title: "百分数",
      knowledge_point: "百分数的意义",
      textbook_file: { name: "百分数.pdf", size: 1024, type: "application/pdf" },
    });

    saveMockDraft(`lesson-plan:${project.id}`, { objective: "理解百分数" });

    const restored = createMockRuntimeStore({ storage: localStorage });
    expect(restored.getState().projects).toHaveLength(9);
    expect(getMockProject(project.id, restored)).toMatchObject({ title: "百分数" });
    expect(restored.getState().textbookFiles[project.id]?.[0]).toMatchObject({
      name: "百分数.pdf",
    });
    expect(restored.getState().drafts[`lesson-plan:${project.id}`]).toMatchObject({
      value: { objective: "理解百分数" },
    });
  });

  it("creates a project and its textbook file in one persisted notification", () => {
    const setItem = vi.fn();
    const storage: Storage = {
      clear: vi.fn(),
      getItem: vi.fn(() => null),
      key: vi.fn(() => null),
      length: 0,
      removeItem: vi.fn(),
      setItem,
    };
    const store = createMockRuntimeStore({ storage });
    const snapshots: ReturnType<typeof store.getState>[] = [];
    store.subscribe(() => snapshots.push(structuredClone(store.getState())));

    const project = store.createProject({
      title: "小数乘法",
      knowledge_point: "小数乘法的意义",
      textbook_file: { name: "小数乘法.pdf", size: 2048, type: "application/pdf" },
    });

    expect(setItem).toHaveBeenCalledTimes(1);
    expect(snapshots).toHaveLength(1);
    expect(snapshots[0]?.projects.some((item) => item.id === project.id)).toBe(true);
    expect(snapshots[0]?.textbookFiles[project.id]).toEqual([
      expect.objectContaining({ name: "小数乘法.pdf", project_id: project.id }),
    ]);
  });

  it("notifies subscribers when a project is updated", () => {
    const store = createMockRuntimeStore({ storage: localStorage });
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);
    store.updateProject("01960000-0000-7000-8000-000000000001", { title: "新标题" });
    unsubscribe();
    expect(listener).toHaveBeenCalledTimes(1);
    expect(store.getState().projects[0]?.title).toBe("新标题");
  });

  it("falls back to the demo seed when persisted data is malformed", () => {
    localStorage.setItem(
      "shanhaiedu.mock-runtime.v1",
      JSON.stringify({ schemaVersion: 1, projects: [], textbookFiles: {}, nodeStates: {} }),
    );
    const store = createMockRuntimeStore({ storage: localStorage });
    expect(store.getState().projects).toHaveLength(8);
    expect(store.getState().session).toBeNull();
  });

  it("normalizes workflow statuses added by a newer server or older cache", () => {
    const persisted = createDefaultMockRuntimeState() as unknown as {
      nodeStates: Record<string, { status: string }>;
      tasks: Array<{ status: string }>;
    };
    const node = Object.values(persisted.nodeStates)[0];
    const task = persisted.tasks[0];
    expect(node).toBeDefined();
    expect(task).toBeDefined();
    if (!node || !task) throw new Error("默认 Mock 状态缺少节点或任务");
    node.status = "future_node_status";
    task.status = "future_task_status";
    localStorage.setItem("shanhaiedu.mock-runtime.v1", JSON.stringify(persisted));

    const restored = createMockRuntimeStore({ storage: localStorage }).getState();

    expect(Object.values(restored.nodeStates)[0]?.status).toBe("unknown");
    expect(restored.tasks[0]?.status).toBe("unknown");
  });

  it("rejects a nested malformed session instead of exposing it to route guards", () => {
    const malformed = createDefaultMockRuntimeState() as unknown as Record<string, unknown>;
    malformed.session = { expires_at: "not-a-date", user: { role: "owner" } };
    localStorage.setItem("shanhaiedu.mock-runtime.v1", JSON.stringify(malformed));

    const store = createMockRuntimeStore({ storage: localStorage });
    expect(store.getState().session).toBeNull();
    expect(store.getState().projects).toHaveLength(8);
  });

  it("clears a stale reason when an explicit null patch is supplied", () => {
    const store = createMockRuntimeStore({ storage: localStorage });
    store.updateNodeState("project-a", "lesson-a", "lesson-plan", {
      stale_reason: { summary: "上游内容已更新" },
      status: "stale",
    });
    store.updateNodeState("project-a", "lesson-a", "lesson-plan", {
      stale_reason: null,
      status: "approved",
    });
    expect(store.getNodeState("project-a", "lesson-a", "lesson-plan")?.stale_reason).toBeNull();
  });

  it("reports storage failures without mutating memory or notifying subscribers", () => {
    const failingStorage: Storage = {
      clear: vi.fn(),
      getItem: vi.fn(() => null),
      key: vi.fn(() => null),
      length: 0,
      removeItem: vi.fn(),
      setItem: vi.fn(() => {
        throw new DOMException("Quota exceeded", "QuotaExceededError");
      }),
    };
    const store = createMockRuntimeStore({
      seed: createDefaultMockRuntimeState(),
      storage: failingStorage,
    });
    const before = structuredClone(store.getState());
    const listener = vi.fn();
    store.subscribe(listener);

    expect(() =>
      store.createProject({
        title: "不会保存",
        knowledge_point: "持久化失败",
        textbook_file: { name: "失败.pdf", size: 1024, type: "application/pdf" },
      }),
    ).toThrow(MockRuntimeStorageError);
    expect(store.getState()).toEqual(before);
    expect(listener).not.toHaveBeenCalled();
  });

  it("updates from the current snapshot without cloning the complete state first", () => {
    const store = createMockRuntimeStore({ storage: localStorage });
    const before = store.getState();
    const projects = before.projects;

    store.setState((current) => ({
      ...current,
      tasks: current.tasks.map((task) =>
        task.id === current.tasks[0]?.id ? { ...task, progress: task.progress + 1 } : task,
      ),
    }));

    expect(store.getState()).not.toBe(before);
    expect(store.getState().projects).toBe(projects);
  });

  it("moves a cancelled final-video task to its terminal state", async () => {
    vi.useFakeTimers();
    try {
      const store = createMockRuntimeStore({ storage: localStorage });
      const node = store.updateNodeState("project-a", "lesson-a", "final-video", {
        status: "running",
      });
      const task = store.createTask({
        detail: "合成中",
        node_run_id: node.id,
        project_id: "project-a",
        stage: "合成中",
        status: "running",
        title: "成片合成",
      });

      store.updateTask(task.id, { status: "cancel_requested" });
      await vi.advanceTimersByTimeAsync(200);

      expect(store.getState().tasks.find((item) => item.id === task.id)?.status).toBe("cancelled");
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("mock authentication", () => {
  beforeEach(() => {
    localStorage.clear();
    resetMockRuntime();
    signOut();
  });

  it("persists a teacher session and clears it on sign out", () => {
    const session = signIn({ email: "lin.teacher@example.edu", password: "teacher-demo" });
    expect(session.user.role).toBe("teacher");
    expect(getMockSession()?.user.email).toBe("lin.teacher@example.edu");
    expect(createMockRuntimeStore({ storage: localStorage }).getState().session?.user.role).toBe(
      "teacher",
    );
    signOut();
    expect(getMockSession()).toBeNull();
    expect(createMockRuntimeStore({ storage: localStorage }).getState().session).toBeNull();
  });

  it("distinguishes the admin account and rejects invalid credentials", () => {
    signIn("admin@example.edu", "admin-demo");
    expect(hasMockRole("admin")).toBe(true);
    signOut();
    expect(() => signIn("admin@example.edu", "wrong-password")).toThrow(MockAuthError);
  });

  it("allows mock authentication only in development mock mode", () => {
    expect(canUseMockAuth({ development: true, mode: "mock" })).toBe(true);
    expect(canUseMockAuth({ development: true, mode: "real" })).toBe(false);
    expect(canUseMockAuth({ development: false, mode: "mock" })).toBe(false);
    const session = createMockSession("teacher");
    expect(resolveMockSessionSnapshot(session, false)).toBeNull();
  });

  it("reads an expired session without mutating the runtime snapshot", () => {
    const session = createMockSession("teacher");
    mockRuntime.setSession({ ...session, expires_at: "2000-01-01T00:00:00.000Z" });
    const listener = vi.fn();
    const unsubscribe = mockRuntime.subscribe(listener);
    expect(getMockSession()).toBeNull();
    unsubscribe();
    expect(listener).not.toHaveBeenCalled();
    expect(mockRuntime.getState().session?.id).toBe(session.id);
  });
});
