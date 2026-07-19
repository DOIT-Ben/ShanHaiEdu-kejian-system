import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { lessons, demoProjectId } from "@/shared/data/mockData";
import { ProjectMaterialsPage } from "@/pages/projects/ProjectMaterialsPage";
import {
  mockRuntime,
  addMockTextbookFile,
  createMockProject,
  resetMockRuntime,
  saveMockDraft,
  updateMockNodeState,
} from "@/shared/api/mocks/runtime";

describe("ProjectMaterialsPage approved editing", () => {
  beforeEach(() => resetMockRuntime());

  it("批准后的课时安排锁定，重新编辑后才允许修改", () => {
    saveMockDraft(`project:${demoProjectId}:lessons`, lessons, {
      projectId: demoProjectId,
      nodeKey: "lesson-division",
    });
    updateMockNodeState(demoProjectId, null, "lesson-division", {
      status: "approved",
      title: "安排课时",
    });

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/projects/${demoProjectId}/materials`]}>
          <Routes>
            <Route element={<ProjectMaterialsPage />} path="/projects/:projectId/materials" />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    expect(screen.getByRole("button", { name: "重新编辑课时" })).toBeInTheDocument();
    expect(screen.getAllByRole("textbox").every((input) => input.hasAttribute("disabled"))).toBe(
      true,
    );
    fireEvent.click(screen.getByRole("button", { name: "重新编辑课时" }));
    expect(screen.getAllByRole("textbox")[0]).not.toBeDisabled();
  });

  it("多个教材文件中只要有一个已整理就使用该文件并开放批准", () => {
    mockRuntime.setState((current) => {
      const source = current.textbookFiles[demoProjectId]?.[0];
      if (!source) return current;
      return {
        ...current,
        nodeStates: Object.fromEntries(
          Object.entries(current.nodeStates).filter(
            ([key]) => key !== `${demoProjectId}:*:lesson-division`,
          ),
        ),
        textbookFiles: {
          ...current.textbookFiles,
          [demoProjectId]: [
            { ...source, id: "processing-file", name: "正在整理.pdf", status: "processing" },
            { ...source, id: "ready-file", name: "已整理教材.pdf", status: "ready" },
          ],
        },
      };
    });

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/projects/${demoProjectId}/materials`]}>
          <Routes>
            <Route element={<ProjectMaterialsPage />} path="/projects/:projectId/materials" />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    expect(screen.getByRole("heading", { name: "已整理教材.pdf" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "批准课时安排" })).toBeEnabled();
  });

  it("新项目上传教材后会从整理中进入已准备", async () => {
    const project = createMockProject({
      knowledge_point: "分数的意义",
      title: "新项目",
    });
    addMockTextbookFile(project.id, {
      name: "新教材.pdf",
      size: 1024,
      type: "application/pdf",
    });

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/projects/${project.id}/materials`]}>
          <Routes>
            <Route element={<ProjectMaterialsPage />} path="/projects/:projectId/materials" />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    const approve = screen.getByRole("button", { name: "批准课时安排" });
    expect(approve).toBeDisabled();
    await waitFor(() => expect(approve).toBeEnabled(), { timeout: 1500 });
    expect(screen.getByText("教材已准备")).toBeInTheDocument();
  });

  it("教材读取失败后可以在原页重新上传并恢复", async () => {
    mockRuntime.setState((current) => ({
      ...current,
      nodeStates: Object.fromEntries(
        Object.entries(current.nodeStates).filter(
          ([key]) => key !== `${demoProjectId}:*:lesson-division`,
        ),
      ),
      textbookFiles: {
        ...current.textbookFiles,
        [demoProjectId]: (current.textbookFiles[demoProjectId] ?? []).map((file) => ({
          ...file,
          status: "failed" as const,
        })),
      },
    }));

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={[`/projects/${demoProjectId}/materials`]}>
          <Routes>
            <Route element={<ProjectMaterialsPage />} path="/projects/:projectId/materials" />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    expect(screen.getByText("读取失败")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "批准课时安排" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("重新上传教材文件"), {
      target: {
        files: [new File(["mock pdf"], "替换教材.pdf", { type: "application/pdf" })],
      },
    });

    await waitFor(
      () => expect(screen.getByRole("button", { name: "批准课时安排" })).toBeEnabled(),
      { timeout: 1500 },
    );
    expect(screen.getByRole("heading", { name: "替换教材.pdf" })).toBeInTheDocument();
  });
});
