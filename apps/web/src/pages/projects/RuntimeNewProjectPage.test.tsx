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
  fileSnapshot,
  readRuntimeNewProjectRecovery,
  runtimeNewProjectFingerprint,
  writeRuntimeNewProjectRecovery,
  type RuntimeNewProjectForm,
} from "@/pages/projects/runtimeNewProjectRecovery";
import { ApiError, configureCsrfTokenProvider } from "@/shared/api/client";

const savedForm: RuntimeNewProjectForm = {
  executionMode: "guided",
  grade: "六年级",
  knowledgePoint: "百分数的意义",
  sourceMode: "textbook",
  textbookEdition: "人教版",
  title: "认识百分数",
};

function expiredConfirmingRecovery(file: File) {
  const sha256 = "a".repeat(64);
  const snapshot = { ...fileSnapshot(file), sha256 };
  return {
    sha256,
    stored: {
      ...createRuntimeNewProjectRecovery(savedForm),
      etag: '"material-v1"',
      file: snapshot,
      fingerprint: runtimeNewProjectFingerprint(savedForm, snapshot),
      intent: {
        confirm: "confirm-original",
        project: "project-original",
        upload: "upload-original",
      },
      projectId: "01960000-0000-7000-8000-000000000001",
      stage: "confirming" as const,
      uploadSession: {
        expires_at: "2020-01-01T00:00:00Z",
        material_id: "01960000-0000-7000-8000-000000000004",
        method: "PUT" as const,
        required_headers: { "Content-Type": "application/pdf" },
        upload_session_id: "01960000-0000-7000-8000-000000000002",
        upload_url: "https://upload.example.test/material",
      },
    },
  };
}

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
          <Route element={<p>教材任务已建立</p>} path="/app/projects/:projectId/setup" />
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
    expect(screen.getByRole("combobox", { name: "年级" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "教材版本" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /边看边确认/ })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /自动推进/ })).toBeDisabled();
    expect(fileInput).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "移除教材文件" })).toBeDisabled();
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

  it("clears a textbook file error after switching to anchor-only mode", async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderPage();

    await user.upload(
      screen.getByLabelText(/选择 PDF 教材/),
      new File(["not-a-pdf"], "教材.txt", { type: "text/plain" }),
    );
    expect(screen.getByText("目前只支持 PDF 教材")).toBeVisible();

    await user.click(screen.getByRole("radio", { name: /暂不使用教材/ }));

    expect(screen.queryByText("目前只支持 PDF 教材")).not.toBeInTheDocument();
  });

  it("allows an anchor-only project to omit the optional textbook edition", async () => {
    const user = userEvent.setup();
    const createProject = vi.spyOn(projectsApi, "createProject").mockResolvedValue({
      id: "01960000-0000-7000-8000-000000000223",
    } as Awaited<ReturnType<typeof projectsApi.createProject>>);
    renderPage();

    await user.click(screen.getByRole("radio", { name: /暂不使用教材/ }));
    await user.type(screen.getByLabelText("项目名称"), "生活中的百分数");
    await user.type(screen.getByLabelText("知识点"), "百分数的实际应用");
    await user.click(screen.getByRole("combobox", { name: "教材版本" }));
    await user.click(screen.getByRole("option", { name: "不指定教材版本" }));

    expect(screen.getByRole("region", { name: "课程锚点摘要" })).toHaveTextContent(
      "六年级 · 未指定教材版本 · 百分数的实际应用",
    );
    await user.click(screen.getByRole("button", { name: "创建课程项目" }));

    expect(await screen.findByText("项目创建完成")).toBeVisible();
    const request = createProject.mock.calls[0]?.[0];
    expect(request?.input).not.toHaveProperty("textbook_edition");
  });

  it("applies the shared PDF extension and non-empty rules before hashing", async () => {
    const user = userEvent.setup({ applyAccept: false });
    const sha256 = vi.spyOn(materialsApi, "sha256File");
    renderPage();
    const fileInput = screen.getByLabelText(/选择 PDF 教材/);

    await user.upload(fileInput, new File([], "教材.pdf", { type: "application/pdf" }));
    expect(screen.getByText("教材文件不能为空")).toBeVisible();
    expect(sha256).not.toHaveBeenCalled();

    await user.upload(fileInput, new File(["pdf"], "教材.pdf", { type: "" }));
    expect(screen.getByRole("button", { name: "移除教材文件" })).toBeVisible();
    expect(screen.queryByText("目前只支持 PDF 教材")).not.toBeInTheDocument();
  });

  it("retries an expired confirmation with the original intent after a lost response", async () => {
    const user = userEvent.setup();
    const file = new File(["textbook"], "百分数.pdf", {
      lastModified: 1_720_000_000_000,
      type: "application/pdf",
    });
    const { sha256, stored } = expiredConfirmingRecovery(file);
    writeRuntimeNewProjectRecovery(stored);
    vi.spyOn(materialsApi, "sha256File").mockResolvedValue(sha256);
    const createUpload = vi.spyOn(materialsApi, "createMaterialUploadSession");
    const uploadFile = vi.spyOn(materialsApi, "uploadMaterialFile");
    const confirmUpload = vi.spyOn(materialsApi, "confirmMaterialUpload").mockResolvedValue({
      events_url: "/api/v2/generation-jobs/01960000-0000-7000-8000-000000000003/events/stream",
      job_id: "01960000-0000-7000-8000-000000000003",
      status: "queued",
    });
    renderPage();

    expect(readRuntimeNewProjectRecovery()).toMatchObject({
      etag: stored.etag,
      intent: stored.intent,
      stage: "confirming",
      uploadSession: stored.uploadSession,
    });
    await user.upload(screen.getByLabelText(/重新选择同一份 PDF/), file);
    await waitFor(() =>
      expect(readRuntimeNewProjectRecovery()).toMatchObject({
        etag: stored.etag,
        intent: stored.intent,
        stage: "confirming",
        uploadSession: stored.uploadSession,
      }),
    );
    await user.click(screen.getByRole("button", { name: "创建项目并上传教材" }));

    await waitFor(() =>
      expect(confirmUpload).toHaveBeenCalledWith(
        expect.objectContaining({
          idempotencyKey: "confirm-original",
          uploadSessionId: stored.uploadSession.upload_session_id,
        }),
      ),
    );
    expect(createUpload).not.toHaveBeenCalled();
    expect(uploadFile).not.toHaveBeenCalled();
  });

  it("starts a new upload intent only after the server explicitly rejects confirmation", async () => {
    const user = userEvent.setup();
    const file = new File(["textbook"], "百分数.pdf", {
      lastModified: 1_720_000_000_000,
      type: "application/pdf",
    });
    const { sha256, stored } = expiredConfirmingRecovery(file);
    writeRuntimeNewProjectRecovery(stored);
    vi.spyOn(materialsApi, "sha256File").mockResolvedValue(sha256);
    vi.spyOn(materialsApi, "confirmMaterialUpload").mockRejectedValue(
      new ApiError({
        error: {
          code: "UPLOAD_REJECTED",
          message: "The upload session is no longer confirmable.",
          retryable: false,
        },
        request_id: "request-confirm-rejected",
      }),
    );
    renderPage();

    await user.upload(screen.getByLabelText(/重新选择同一份 PDF/), file);
    await user.click(screen.getByRole("button", { name: "创建项目并上传教材" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("教材上传状态已失效，请重新提交");
    const restarted = readRuntimeNewProjectRecovery();
    expect(restarted?.projectId).toBe(stored.projectId);
    expect(restarted?.intent.project).toBe(stored.intent.project);
    expect(restarted?.intent.upload).not.toBe(stored.intent.upload);
    expect(restarted?.intent.confirm).not.toBe(stored.intent.confirm);
    expect(restarted?.uploadSession).toBeUndefined();
    expect(restarted?.etag).toBeUndefined();
  });

  it("keeps the original confirmation intent after a retryable network failure", async () => {
    const user = userEvent.setup();
    const file = new File(["textbook"], "百分数.pdf", {
      lastModified: 1_720_000_000_000,
      type: "application/pdf",
    });
    const { sha256, stored } = expiredConfirmingRecovery(file);
    writeRuntimeNewProjectRecovery(stored);
    vi.spyOn(materialsApi, "sha256File").mockResolvedValue(sha256);
    const confirmUpload = vi.spyOn(materialsApi, "confirmMaterialUpload").mockRejectedValue(
      new ApiError({
        error: {
          code: "NETWORK_ERROR",
          message: "网络连接失败，请检查网络后重试",
          retryable: true,
        },
        request_id: "unknown",
      }),
    );
    renderPage();

    await user.upload(screen.getByLabelText(/重新选择同一份 PDF/), file);
    await user.click(screen.getByRole("button", { name: "创建项目并上传教材" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("网络连接失败，请检查网络后重试");
    expect(confirmUpload).toHaveBeenCalledWith(
      expect.objectContaining({ idempotencyKey: stored.intent.confirm }),
    );
    const persisted = readRuntimeNewProjectRecovery();
    expect(persisted?.intent).toEqual(stored.intent);
    expect(persisted?.uploadSession).toEqual(stored.uploadSession);
    expect(persisted?.etag).toBe(stored.etag);
  });
});
