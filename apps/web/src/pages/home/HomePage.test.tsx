import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { HomePage } from "@/pages/home/HomePage";

vi.mock("@/features/projects/hooks/useProjectsQuery", () => ({
  useProjectsQuery: vi.fn(),
}));

const mockUseProjectsQuery = vi.mocked(useProjectsQuery);

function renderHome() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  );
}

describe("HomePage", () => {
  beforeEach(() => {
    mockUseProjectsQuery.mockReset();
  });

  it("首页不直接读取 Mock 运行时或 Mock 身份", () => {
    const source = readFileSync(resolve(__dirname, "HomePage.tsx"), "utf8");

    expect(source).not.toContain("useMockRuntime");
    expect(source).not.toContain("useMockSession");
    expect(source).not.toContain("@/shared/api/mocks");
    expect(source).not.toContain("@/shared/auth/mockAuth");
  });

  it("只使用项目视图模型展示续作，不伪造身份、完成度或项目预览", () => {
    mockUseProjectsQuery.mockReturnValue({
      data: [
        {
          archived: false,
          currentLesson: "第 1 课时 · 百分数的意义",
          grade: "六年级",
          id: "project-1",
          knowledgePoint: "百分数的意义",
          nextAction: "继续当前课时制作",
          progressLabel: "制作中",
          status: "active",
          textbookEdition: "人教版",
          title: "认识百分数",
          updatedAt: "7月20日",
        },
      ],
      isError: false,
      isLoading: false,
    } as unknown as ReturnType<typeof useProjectsQuery>);

    renderHome();

    expect(screen.getByText("山海教育 · 课堂创作空间")).toBeInTheDocument();
    expect(screen.queryByText(/老师|管理员/)).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByText("62%")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /继续制作/ })).toHaveAttribute(
      "href",
      "/app/projects/project-1",
    );
  });

  it("生产摘要缺少工作流聚合字段时只展示真实知识点", () => {
    mockUseProjectsQuery.mockReturnValue({
      data: [
        {
          archived: false,
          grade: "六年级",
          id: "project-runtime",
          knowledgePoint: "百分数的意义",
          progressLabel: "草稿",
          status: "draft",
          textbookEdition: "人教版",
          title: "认识百分数",
          updatedAt: "7月20日",
        },
      ],
      isError: false,
      isLoading: false,
    } as unknown as ReturnType<typeof useProjectsQuery>);

    renderHome();

    expect(screen.getByText("百分数的意义")).toBeInTheDocument();
    expect(screen.queryByText(/下一步/)).not.toBeInTheDocument();
    expect(screen.queryByText(/第 1 课时/)).not.toBeInTheDocument();
  });

  it("没有项目时明确引导创建，PPT 入口只说明后续开放", () => {
    mockUseProjectsQuery.mockReturnValue({
      data: [],
      isError: false,
      isLoading: false,
    } as unknown as ReturnType<typeof useProjectsQuery>);

    renderHome();

    expect(screen.getByRole("link", { name: "创建第一个项目" })).toHaveAttribute(
      "href",
      "/app/projects/new",
    );
    expect(screen.getByRole("img", { name: "等待开始备课的温暖书桌" })).toBeInTheDocument();
    expect(screen.getByText("后续开放")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /完成一套课堂课件/ })).not.toBeInTheDocument();
  });
});
