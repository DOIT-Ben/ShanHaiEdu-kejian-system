import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as materialsApi from "@/features/materials/api/materialsApi";
import * as projectsApi from "@/features/projects/api/projectsApi";
import { RuntimeNewProjectPage } from "@/pages/projects/RuntimeNewProjectPage";
import {
  createRuntimeNewProjectRecovery,
  readRuntimeNewProjectRecovery,
  runtimeNewProjectFingerprint,
  writeRuntimeNewProjectRecovery,
  type RuntimeNewProjectForm,
} from "@/pages/projects/runtimeNewProjectRecovery";
import { configureCsrfTokenProvider } from "@/shared/api/client";

const savedForm: RuntimeNewProjectForm = {
  executionMode: "guided",
  grade: "六年级",
  knowledgePoint: "百分数的意义",
  sourceMode: "textbook",
  textbookEdition: "人教版",
  title: "认识百分数",
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/app/projects/new"]}>
        <Routes>
          <Route element={<RuntimeNewProjectPage />} path="/app/projects/new" />
          <Route element={<p>项目创建完成</p>} path="/app/projects/:projectId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RuntimeNewProjectPage recovery", () => {
  beforeEach(() => {
    sessionStorage.clear();
    configureCsrfTokenProvider(() => "csrf-test-token");
  });

  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.restoreAllMocks();
  });

  it("hydrates the saved form and explains how a pending upload resumes", () => {
    const file = {
      lastModified: 1_720_000_000_000,
      name: "百分数.pdf",
      sha256: "abc123",
      size: 4_096,
      type: "application/pdf",
    };
    writeRuntimeNewProjectRecovery({
      ...createRuntimeNewProjectRecovery(savedForm),
      file,
      fingerprint: runtimeNewProjectFingerprint(savedForm, file),
      projectId: "01960000-0000-7000-8000-000000000001",
      stage: "uploading",
    });

    renderPage();

    expect(screen.getByLabelText("项目名称")).toHaveValue("认识百分数");
    expect(screen.getByLabelText("知识点")).toHaveValue("百分数的意义");
    expect(screen.getByRole("status", { name: "已保存的课程进度" })).toHaveTextContent(
      "重新选择同一份 PDF 后可以继续上传",
    );
    expect(screen.getByText("重新选择同一份 PDF")).toBeVisible();
  });

  it("drops old server identifiers when the restored form is changed", async () => {
    const user = userEvent.setup();
    const file = {
      lastModified: 1_720_000_000_000,
      name: "百分数.pdf",
      sha256: "abc123",
      size: 4_096,
      type: "application/pdf",
    };
    writeRuntimeNewProjectRecovery({
      ...createRuntimeNewProjectRecovery(savedForm),
      etag: '"material-v1"',
      file,
      fingerprint: runtimeNewProjectFingerprint(savedForm, file),
      projectId: "01960000-0000-7000-8000-000000000001",
      stage: "uploading",
      uploadSession: {
        expires_at: "2030-01-01T00:00:00Z",
        material_id: "01960000-0000-7000-8000-000000000004",
        method: "PUT",
        required_headers: { "Content-Type": "application/pdf" },
        upload_session_id: "01960000-0000-7000-8000-000000000002",
        upload_url: "https://upload.example.test/material",
      },
    });
    renderPage();

    const title = screen.getByLabelText("项目名称");
    await user.clear(title);
    await user.type(title, "百分数新课");

    await waitFor(() => {
      const recovery = readRuntimeNewProjectRecovery();
      expect(recovery?.form.title).toBe("百分数新课");
      expect(recovery?.projectId).toBeUndefined();
      expect(recovery?.uploadSession).toBeUndefined();
      expect(recovery?.etag).toBeUndefined();
    });
  });

  it("freezes the active intent while project creation and upload are in flight", async () => {
    const user = userEvent.setup();
    vi.spyOn(materialsApi, "sha256File").mockResolvedValue("a".repeat(64));
    vi.spyOn(projectsApi, "createProject").mockResolvedValue({
      id: "01960000-0000-7000-8000-000000000111",
    } as Awaited<ReturnType<typeof projectsApi.createProject>>);
    vi.spyOn(materialsApi, "createMaterialUploadSession").mockImplementation(
      () => new Promise(() => undefined),
    );
    renderPage();

    await user.type(screen.getByLabelText("项目名称"), "认识百分数");
    await user.type(screen.getByLabelText("知识点"), "百分数的意义");
    const fileInput = screen.getByLabelText(/选择 PDF 教材/);
    await user.upload(
      fileInput,
      new File(["textbook"], "百分数.pdf", {
        lastModified: 1_720_000_000_000,
        type: "application/pdf",
      }),
    );
    await user.click(screen.getByRole("button", { name: "创建项目并上传教材" }));

    expect(await screen.findByRole("button", { name: "正在上传教材" })).toBeDisabled();
    expect(screen.getByLabelText("项目名称")).toBeDisabled();
    expect(screen.getByLabelText("知识点")).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "选择年级" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "选择教材版本" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "选择制作方式" })).toBeDisabled();
    expect(fileInput).toBeDisabled();
    expect(screen.getByRole("button", { name: "重新开始" })).toBeDisabled();
  });

  it("creates an anchor-only project without inventing a material upload", async () => {
    const user = userEvent.setup();
    const createProject = vi.spyOn(projectsApi, "createProject").mockResolvedValue({
      id: "01960000-0000-7000-8000-000000000222",
    } as Awaited<ReturnType<typeof projectsApi.createProject>>);
    const createUpload = vi.spyOn(materialsApi, "createMaterialUploadSession");
    renderPage();

    await user.click(screen.getByRole("radio", { name: /暂不使用教材/ }));
    await user.type(screen.getByLabelText("项目名称"), "生活中的百分数");
    await user.type(screen.getByLabelText("知识点"), "百分数的实际应用");

    expect(screen.getByRole("region", { name: "课程锚点摘要" })).toHaveTextContent(
      "六年级 · 人教版 · 百分数的实际应用",
    );
    await user.click(screen.getByRole("button", { name: "创建课程项目" }));

    expect(await screen.findByText("项目创建完成")).toBeVisible();
    expect(createProject).toHaveBeenCalledWith(
      expect.objectContaining({
        input: {
          execution_mode: "guided",
          grade: "六年级",
          knowledge_point: "百分数的实际应用",
          textbook_edition: "人教版",
          title: "生活中的百分数",
        },
      }),
    );
    expect(createUpload).not.toHaveBeenCalled();
  });
});
