import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { ProjectsPage } from "@/pages/projects/ProjectsPage";

vi.mock("@/features/projects/hooks/useProjectsQuery", () => ({
  useProjectsQuery: vi.fn(),
}));

const mockUseProjectsQuery = vi.mocked(useProjectsQuery);

describe("ProjectsPage", () => {
  it("用紧凑行式列表按最近活动展示八个项目", () => {
    mockUseProjectsQuery.mockReturnValue({
      data: Array.from({ length: 8 }, (_, index) => ({
        archived: false,
        currentLesson: `第 ${String(index + 1)} 课时`,
        grade: "六年级",
        id: `project-${String(index + 1)}`,
        knowledgePoint: `知识点 ${String(index + 1)}`,
        nextAction: `继续任务 ${String(index + 1)}`,
        progressLabel: "进行中",
        status: "active" as const,
        textbookEdition: "人教版",
        title: `课题 ${String(index + 1)}`,
        updatedAt: `7月${String(index + 1)}日`,
        updatedAtIso: `2026-07-${String(index + 1).padStart(2, "0")}T08:00:00Z`,
      })),
      hasNextPage: false,
      isError: false,
      isFetching: false,
      isLoading: false,
    } as unknown as ReturnType<typeof useProjectsQuery>);

    render(
      <MemoryRouter>
        <ProjectsPage />
      </MemoryRouter>,
    );

    const rows = screen.getAllByTestId("project-row");
    expect(rows).toHaveLength(8);
    const firstRow = rows[0];
    if (!firstRow) throw new Error("项目列表缺少第一行");
    expect(within(firstRow).getByText("课题 8")).toBeInTheDocument();
    expect(within(firstRow).getByText("第 8 课时")).toBeInTheDocument();
    expect(within(firstRow).getByText("继续任务 8")).toBeInTheDocument();
    expect(within(firstRow).getByText("进行中")).toBeInTheDocument();

    const toolbar = screen.getByRole("banner");
    expect(within(toolbar).getByRole("searchbox", { name: "搜索项目" })).toBeInTheDocument();
    expect(within(toolbar).getByRole("link", { name: "创建项目" })).toBeInTheDocument();
  });

  it("搜索同时覆盖课题、知识点、课时和下一步", () => {
    mockUseProjectsQuery.mockReturnValue({
      data: [
        {
          archived: false,
          currentLesson: "第 2 课时 · 面积公式应用",
          grade: "五年级",
          id: "project-area",
          knowledgePoint: "平行四边形面积",
          nextAction: "选择 PPT 封面",
          progressLabel: "进行中",
          status: "active",
          textbookEdition: "苏教版",
          title: "面积课",
          updatedAt: "7月20日",
        },
      ],
      hasNextPage: false,
      isError: false,
      isFetching: false,
      isLoading: false,
    } as unknown as ReturnType<typeof useProjectsQuery>);

    render(
      <MemoryRouter>
        <ProjectsPage />
      </MemoryRouter>,
    );
    const search = screen.getByRole("searchbox", { name: "搜索项目" });

    fireEvent.change(search, { target: { value: "PPT 封面" } });
    expect(screen.getAllByTestId("project-row")).toHaveLength(1);
    fireEvent.change(search, { target: { value: "圆的认识" } });
    expect(screen.queryByTestId("project-row")).not.toBeInTheDocument();
  });
});
