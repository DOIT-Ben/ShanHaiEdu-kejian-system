import { beforeEach, describe, expect, it } from "vitest";
import {
  RUNTIME_NEW_PROJECT_RECOVERY_KEY,
  createRuntimeNewProjectRecovery,
  fileSnapshot,
  readRuntimeNewProjectRecovery,
  refreshExpiredRuntimeUploadSession,
  restartRuntimeMaterialUpload,
  runtimeNewProjectFingerprint,
  sameFileSnapshot,
  withNewRuntimeNewProjectIntent,
  writeRuntimeNewProjectRecovery,
  type RuntimeNewProjectForm,
} from "@/pages/projects/runtimeNewProjectRecovery";

const form: RuntimeNewProjectForm = {
  executionMode: "guided",
  grade: "六年级",
  knowledgePoint: "百分数的意义",
  sourceMode: "textbook",
  textbookEdition: "人教版",
  title: "认识百分数",
};

describe("runtime new-project recovery", () => {
  beforeEach(() => sessionStorage.clear());

  it("persists the intent and every server-side recovery identifier", () => {
    const recovery = {
      ...createRuntimeNewProjectRecovery(form),
      etag: '"material-v1"',
      file: {
        lastModified: 1_720_000_000_000,
        name: "百分数.pdf",
        sha256: "abc123",
        size: 4_096,
        type: "application/pdf",
      },
      fingerprint: "stable-fingerprint",
      jobId: "01960000-0000-7000-8000-000000000003",
      projectId: "01960000-0000-7000-8000-000000000001",
      stage: "confirming" as const,
      uploadSession: {
        expires_at: "2030-01-01T00:00:00Z",
        material_id: "01960000-0000-7000-8000-000000000004",
        method: "PUT" as const,
        required_headers: { "Content-Type": "application/pdf" },
        upload_session_id: "01960000-0000-7000-8000-000000000002",
        upload_url: "https://upload.example.test/material",
      },
    };

    writeRuntimeNewProjectRecovery(recovery);

    expect(readRuntimeNewProjectRecovery()).toEqual(recovery);
  });

  it("ignores a malformed record instead of treating it as resumable", () => {
    sessionStorage.setItem(
      RUNTIME_NEW_PROJECT_RECOVERY_KEY,
      JSON.stringify({ version: 1, projectId: "project-without-intent" }),
    );

    expect(readRuntimeNewProjectRecovery()).toBeNull();
  });

  it("restores old records as textbook mode", () => {
    const recovery = createRuntimeNewProjectRecovery(form);
    const legacy = {
      ...recovery,
      form: Object.fromEntries(
        Object.entries(recovery.form).filter(([key]) => key !== "sourceMode"),
      ),
    };
    sessionStorage.setItem(RUNTIME_NEW_PROJECT_RECOVERY_KEY, JSON.stringify(legacy));

    expect(readRuntimeNewProjectRecovery()?.form.sourceMode).toBe("textbook");
  });

  it("keeps the metadata fingerprint stable after the digest is calculated", () => {
    const beforeDigest = {
      lastModified: 1_720_000_000_000,
      name: "百分数.pdf",
      size: 4_096,
      type: "application/pdf",
    };
    const afterDigest = { ...beforeDigest, sha256: "abc123" };

    expect(runtimeNewProjectFingerprint(form, afterDigest)).toBe(
      runtimeNewProjectFingerprint(form, beforeDigest),
    );
    expect(sameFileSnapshot(beforeDigest, afterDigest)).toBe(true);
  });

  it("starts a clean intent when the form or selected file changes", () => {
    const original = createRuntimeNewProjectRecovery(form);
    const nextFile = fileSnapshot(
      new File(["lesson"], "新教材.pdf", {
        lastModified: 1_730_000_000_000,
        type: "application/pdf",
      }),
    );
    const next = withNewRuntimeNewProjectIntent({ ...form, title: "新的课堂项目" }, nextFile);

    expect(next.intent).not.toEqual(original.intent);
    expect(next.projectId).toBeUndefined();
    expect(next.uploadSession).toBeUndefined();
    expect(next.etag).toBeUndefined();
    expect(next.jobId).toBeUndefined();
    expect(next.fingerprint).toBe(runtimeNewProjectFingerprint(next.form, nextFile));
  });

  it("keeps the project but rotates upload recovery before confirmation after a signed URL expires", () => {
    const current = {
      ...createRuntimeNewProjectRecovery(form),
      etag: '"material-v1"',
      projectId: "01960000-0000-7000-8000-000000000001",
      stage: "uploading" as const,
      uploadSession: {
        expires_at: "2026-07-20T07:59:00Z",
        material_id: "01960000-0000-7000-8000-000000000004",
        method: "PUT" as const,
        required_headers: { "Content-Type": "application/pdf" },
        upload_session_id: "01960000-0000-7000-8000-000000000002",
        upload_url: "https://upload.example.test/material",
      },
    };

    const refreshed = refreshExpiredRuntimeUploadSession(
      current,
      Date.parse("2026-07-20T08:00:00Z"),
    );

    expect(refreshed.projectId).toBe(current.projectId);
    expect(refreshed.intent.project).toBe(current.intent.project);
    expect(refreshed.intent.upload).not.toBe(current.intent.upload);
    expect(refreshed.intent.confirm).not.toBe(current.intent.confirm);
    expect(refreshed.uploadSession).toBeUndefined();
    expect(refreshed.etag).toBeUndefined();
    expect(refreshed.jobId).toBeUndefined();
    expect(refreshed.stage).toBe("uploading");
  });

  it("keeps an expired confirmed upload intent so the server can replay a lost response", () => {
    const current = {
      ...createRuntimeNewProjectRecovery(form),
      etag: '"material-v1"',
      projectId: "01960000-0000-7000-8000-000000000001",
      stage: "confirming" as const,
      uploadSession: {
        expires_at: "2026-07-20T07:59:00Z",
        material_id: "01960000-0000-7000-8000-000000000004",
        method: "PUT" as const,
        required_headers: { "Content-Type": "application/pdf" },
        upload_session_id: "01960000-0000-7000-8000-000000000002",
        upload_url: "https://upload.example.test/material",
      },
    };

    const refreshed = refreshExpiredRuntimeUploadSession(
      current,
      Date.parse("2026-07-20T08:00:00Z"),
    );

    expect(refreshed).toBe(current);
    expect(refreshed.intent.confirm).toBe(current.intent.confirm);
    expect(refreshed.uploadSession).toBe(current.uploadSession);
    expect(refreshed.etag).toBe(current.etag);
  });

  it("rotates upload and confirmation intents after an explicit confirmation rejection", () => {
    const current = {
      ...createRuntimeNewProjectRecovery(form),
      etag: '"material-v1"',
      jobId: "01960000-0000-7000-8000-000000000003",
      projectId: "01960000-0000-7000-8000-000000000001",
      stage: "confirming" as const,
      uploadSession: {
        expires_at: "2026-07-20T07:59:00Z",
        material_id: "01960000-0000-7000-8000-000000000004",
        method: "PUT" as const,
        required_headers: { "Content-Type": "application/pdf" },
        upload_session_id: "01960000-0000-7000-8000-000000000002",
        upload_url: "https://upload.example.test/material",
      },
    };

    const restarted = restartRuntimeMaterialUpload(current, Date.parse("2026-07-20T08:00:00Z"));

    expect(restarted.projectId).toBe(current.projectId);
    expect(restarted.intent.project).toBe(current.intent.project);
    expect(restarted.intent.upload).not.toBe(current.intent.upload);
    expect(restarted.intent.confirm).not.toBe(current.intent.confirm);
    expect(restarted.uploadSession).toBeUndefined();
    expect(restarted.etag).toBeUndefined();
    expect(restarted.jobId).toBeUndefined();
    expect(restarted.stage).toBe("uploading");
  });
});
