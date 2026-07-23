import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as lessonsApi from "@/features/lessons/api/lessonsApi";
import { RuntimeLessonsPage } from "@/pages/projects/RuntimeLessonsPage";
import { ApiError, configureCsrfTokenProvider } from "@/shared/api/client";

vi.mock("@/shared/api/useProjectEvents", () => ({ useProjectEvents: vi.fn() }));

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000002";
const lesson = {
  branches: [
    { branch_key: "lesson_plan", enabled: true, settings: {}, workflow_status: "not_ready" },
    { branch_key: "video", enabled: false, settings: {}, workflow_status: "disabled" },
  ],
  estimated_minutes: 40,
  id: lessonId,
  objective_summary: "理解百分数的意义",
  position: 1,
  project_id: projectId,
  scope_summary: "认识百分数",
  title: "百分数的意义",
} as lessonsApi.LessonDto;

describe("RuntimeLessonsPage", () => {
  beforeEach(() => configureCsrfTokenProvider(() => "csrf-test-token"));

  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.restoreAllMocks();
  });

  it("集合和分支写入都会同时失效集合与单课时缓存", async () => {
    vi.spyOn(lessonsApi, "listProjectLessons").mockResolvedValue({
      etag: '"lessons-v3"',
      lessons: [lesson],
      lockVersion: 3,
    });
    vi.spyOn(lessonsApi, "updateProjectLessons").mockResolvedValue({
      etag: '"lessons-v4"',
      lessons: [lesson],
      lockVersion: 4,
    });
    vi.spyOn(lessonsApi, "getLesson").mockResolvedValue({
      etag: '"lesson-v3"',
      lesson,
    });
    vi.spyOn(lessonsApi, "updateLessonBranches").mockResolvedValue({
      etag: '"lesson-v4"',
      lesson,
    });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/app/projects/${projectId}/lessons`]}>
          <Routes>
            <Route element={<RuntimeLessonsPage />} path="/app/projects/:projectId/lessons" />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "保存课时集合" }));
    await waitFor(() =>
      expect(invalidateQueries).toHaveBeenCalledWith({
        exact: true,
        queryKey: ["projects", projectId, "lessons"],
      }),
    );
    expect(invalidateQueries).toHaveBeenCalledWith({
      exact: false,
      queryKey: ["lessons"],
    });

    invalidateQueries.mockClear();
    const saveBranches = await screen.findByRole("button", {
      name: "保存百分数的意义的分支",
    });
    await waitFor(() => expect(saveBranches).toBeEnabled());
    await user.click(saveBranches);

    await waitFor(() =>
      expect(invalidateQueries).toHaveBeenCalledWith({
        exact: true,
        queryKey: ["projects", projectId, "lessons"],
      }),
    );
    expect(invalidateQueries).toHaveBeenCalledWith({
      exact: false,
      queryKey: ["lessons"],
    });
  });

  it("集合草稿形成后查询刷新仍使用原始集合 ETag", async () => {
    vi.spyOn(lessonsApi, "listProjectLessons").mockResolvedValue({
      etag: '"lessons-v3"',
      lessons: [lesson],
      lockVersion: 3,
    });
    vi.spyOn(lessonsApi, "getLesson").mockResolvedValue({
      etag: '"lesson-v3"',
      lesson,
    });
    const updateProjectLessons = vi.spyOn(lessonsApi, "updateProjectLessons").mockResolvedValue({
      etag: '"lessons-v5"',
      lessons: [lesson],
      lockVersion: 5,
    });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/app/projects/${projectId}/lessons`]}>
          <Routes>
            <Route element={<RuntimeLessonsPage />} path="/app/projects/:projectId/lessons" />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const user = userEvent.setup();

    const title = await screen.findByLabelText("课时 1 名称");
    await user.clear(title);
    await user.type(title, "尚未保存的集合草稿");
    act(() => {
      queryClient.setQueryData(["projects", projectId, "lessons"], {
        etag: '"lessons-v4"',
        lessons: [{ ...lesson, title: "服务端的新标题" }],
        lockVersion: 4,
      });
    });
    await user.click(screen.getByRole("button", { name: "保存课时集合" }));

    await waitFor(() =>
      expect(updateProjectLessons).toHaveBeenCalledWith(
        expect.objectContaining({ etag: '"lessons-v3"' }),
      ),
    );
  });

  it("分支草稿形成后查询刷新仍使用原始课时 ETag，并保留冲突反馈", async () => {
    vi.spyOn(lessonsApi, "listProjectLessons").mockResolvedValue({
      etag: '"lessons-v3"',
      lessons: [lesson],
      lockVersion: 3,
    });
    const getLesson = vi.spyOn(lessonsApi, "getLesson").mockResolvedValue({
      etag: '"lesson-v3"',
      lesson,
    });
    const updateLessonBranches = vi.spyOn(lessonsApi, "updateLessonBranches").mockRejectedValue(
      new ApiError({
        error: {
          code: "EDIT_CONFLICT",
          message: "课时分支已被更新",
          retryable: false,
        },
        request_id: "lesson-conflict",
      }),
    );
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/app/projects/${projectId}/lessons`]}>
          <Routes>
            <Route element={<RuntimeLessonsPage />} path="/app/projects/:projectId/lessons" />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const user = userEvent.setup();

    const videoBranch = await screen.findByRole("checkbox", { name: "课堂视频" });
    await waitFor(() => expect(videoBranch).toBeEnabled());
    await user.click(videoBranch);
    act(() => {
      queryClient.setQueryData(["lessons", lessonId], {
        etag: '"lesson-v4"',
        lesson: {
          ...lesson,
          branches: lesson.branches.map((branch) =>
            branch.branch_key === "video" ? { ...branch, enabled: true } : branch,
          ),
        },
      });
    });
    getLesson.mockResolvedValue({
      etag: '"lesson-v4"',
      lesson: {
        ...lesson,
        branches: lesson.branches.map((branch) =>
          branch.branch_key === "video" ? { ...branch, enabled: true } : branch,
        ),
      },
    });
    await user.click(screen.getByRole("button", { name: "保存百分数的意义的分支" }));

    await waitFor(() =>
      expect(updateLessonBranches).toHaveBeenCalledWith(
        expect.objectContaining({ etag: '"lesson-v3"' }),
      ),
    );
    expect(getLesson).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("alert")).toHaveTextContent("课时已经被其他操作更新");
  });
});
