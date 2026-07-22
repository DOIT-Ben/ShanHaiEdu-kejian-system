import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import {
  confirmMaterialUpload,
  createMaterialUploadSession,
  sha256File,
  uploadMaterialFile,
  type UploadSessionDto,
} from "@/features/materials/api/materialsApi";
import { createProject } from "@/features/projects/api/projectsApi";
import { projectKeys } from "@/features/projects/hooks/useProjectsQuery";
import { ProjectEntryFrame } from "@/features/projects/components/ProjectEntryFrame";
import {
  ProjectEntryForm,
  type ProjectEntryField,
  type ProjectEntryValues,
} from "@/features/projects/components/ProjectEntryForm";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { Button } from "@/shared/ui/Button";
import {
  clearRuntimeNewProjectRecovery,
  createRuntimeNewProjectRecovery,
  defaultRuntimeNewProjectForm,
  fileSnapshot,
  readRuntimeNewProjectRecovery,
  refreshExpiredRuntimeUploadSession,
  runtimeNewProjectFingerprint,
  sameFileSnapshot,
  withNewRuntimeNewProjectIntent,
  writeRuntimeNewProjectRecovery,
  type RuntimeNewProjectForm,
  type RuntimeNewProjectRecovery,
  type RuntimeNewProjectStage,
} from "@/pages/projects/runtimeNewProjectRecovery";

const projectSchema = z.object({
  executionMode: z.enum(["guided", "automatic"]),
  grade: z.string().min(1, "请选择年级"),
  knowledgePoint: z.string().min(2, "请输入本次要制作的知识点"),
  sourceMode: z.enum(["textbook", "anchor"]),
  textbookEdition: z.string().min(1, "请选择教材版本"),
  title: z.string().min(2, "请输入项目名称"),
});

type ProjectForm = z.infer<typeof projectSchema>;
type SubmitStage = RuntimeNewProjectStage;

const modeOptions = [
  { detail: "每一步都由你确认", label: "边看边确认", value: "guided" },
  { detail: "可随时暂停并回来检查", label: "自动推进", value: "automatic" },
] as const;

const stageLabels: Record<RuntimeNewProjectStage, string> = {
  checking: "正在核对教材",
  confirming: "正在建立课堂任务",
  creating: "正在创建课程",
  idle: "创建项目并上传教材",
  uploading: "正在上传教材",
};

function normalizeForm(
  value: Partial<ProjectForm>,
  fallback: RuntimeNewProjectForm = defaultRuntimeNewProjectForm,
): RuntimeNewProjectForm {
  return {
    executionMode: value.executionMode ?? fallback.executionMode,
    grade: value.grade ?? fallback.grade,
    knowledgePoint: value.knowledgePoint ?? fallback.knowledgePoint,
    sourceMode: value.sourceMode ?? fallback.sourceMode,
    textbookEdition: value.textbookEdition ?? fallback.textbookEdition,
    title: value.title ?? fallback.title,
  };
}

function stageDescription(stage: RuntimeNewProjectStage) {
  switch (stage) {
    case "checking":
      return "正在核对教材文件。重新选择同一份 PDF 后可以继续。";
    case "creating":
      return "课程项目已经开始建立，刷新后不会重复创建。";
    case "uploading":
      return "教材上传尚未完成。重新选择同一份 PDF 后可以继续上传。";
    case "confirming":
      return "教材已经传输，正在建立解析任务。";
    default:
      return "已记住这份教材和课程信息，刷新后可以继续。";
  }
}

export function RuntimeNewProjectPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [initialRecovery] = useState<RuntimeNewProjectRecovery>(() => {
    const stored = readRuntimeNewProjectRecovery();
    if (!stored) return createRuntimeNewProjectRecovery();
    const recovered = refreshExpiredRuntimeUploadSession(stored);
    if (recovered !== stored) writeRuntimeNewProjectRecovery(recovered);
    return recovered;
  });
  const [recovery, setRecovery] = useState(initialRecovery);
  const recoveryRef = useRef(initialRecovery);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState(initialRecovery.errorMessage ?? "");
  const [stage, setStage] = useState<SubmitStage>("idle");

  const replaceRecovery = useCallback((next: RuntimeNewProjectRecovery) => {
    const normalized = { ...next, updatedAt: Date.now() };
    recoveryRef.current = normalized;
    setRecovery(normalized);
    writeRuntimeNewProjectRecovery(normalized);
    return normalized;
  }, []);

  const patchRecovery = useCallback(
    (patch: Partial<RuntimeNewProjectRecovery>) =>
      replaceRecovery({ ...recoveryRef.current, ...patch }),
    [replaceRecovery],
  );

  const {
    formState: { errors },
    getValues,
    handleSubmit,
    reset,
    setValue,
    watch,
  } = useForm<ProjectForm>({
    defaultValues: initialRecovery.form,
    resolver: zodResolver(projectSchema),
  });

  // Keep the editable form in the same recovery record as the server IDs. If
  // the form changes after a project was created, start a fresh intent so a
  // later submit cannot accidentally reuse the previous project.
  useEffect(() => {
    const subscription = watch((values) => {
      const current = recoveryRef.current;
      const form = normalizeForm(values, current.form);
      const recoveryFile = form.sourceMode === "textbook" ? current.file : undefined;
      const fingerprint = runtimeNewProjectFingerprint(form, recoveryFile);
      if (current.projectId && current.fingerprint && fingerprint !== current.fingerprint) {
        replaceRecovery(withNewRuntimeNewProjectIntent(form, recoveryFile));
        return;
      }
      patchRecovery({ file: recoveryFile, form, fingerprint });
    });
    return () => subscription.unsubscribe();
  }, [patchRecovery, replaceRecovery, watch]);

  const resetDraft = useCallback(() => {
    if (stage !== "idle") return;
    clearRuntimeNewProjectRecovery();
    const fresh = createRuntimeNewProjectRecovery();
    recoveryRef.current = fresh;
    setRecovery(fresh);
    setFile(null);
    setMessage("");
    setStage("idle");
    reset(fresh.form);
  }, [reset, stage]);

  const selectFile = useCallback(
    (nextFile: File | null) => {
      if (stage !== "idle") return;
      setFile(nextFile);
      setMessage("");
      if (!nextFile) return;

      const snapshot = fileSnapshot(nextFile);
      const current = recoveryRef.current;
      const form = normalizeForm(getValues(), current.form);
      const fingerprint = runtimeNewProjectFingerprint(form, snapshot);
      if (!sameFileSnapshot(current.file, snapshot) || current.fingerprint !== fingerprint) {
        replaceRecovery(withNewRuntimeNewProjectIntent(form, snapshot));
      } else {
        patchRecovery({
          file: current.file?.sha256 ? { ...snapshot, sha256: current.file.sha256 } : snapshot,
          form,
          errorMessage: undefined,
        });
      }
    },
    [getValues, patchRecovery, replaceRecovery, stage],
  );

  const setSubmitStage = useCallback(
    (nextStage: SubmitStage) => {
      setStage(nextStage);
      return patchRecovery({ stage: nextStage, errorMessage: undefined });
    },
    [patchRecovery],
  );

  const submit = handleSubmit(async (values) => {
    const form = normalizeForm(values);
    if (values.sourceMode === "anchor") {
      let current = recoveryRef.current;
      const fingerprint = runtimeNewProjectFingerprint(form, undefined);
      if (current.fingerprint !== fingerprint || current.file) {
        current = replaceRecovery(withNewRuntimeNewProjectIntent(form, undefined));
      } else {
        current = patchRecovery({ form, errorMessage: undefined });
      }
      setMessage("");
      try {
        current = setSubmitStage("creating");
        const project = await createProject({
          idempotencyKey: current.intent.project,
          input: {
            execution_mode: values.executionMode,
            grade: values.grade,
            knowledge_point: values.knowledgePoint,
            textbook_edition: values.textbookEdition,
            title: values.title,
          },
        });
        current = patchRecovery({ projectId: project.id });
        await queryClient.invalidateQueries({ queryKey: projectKeys.all });
        clearRuntimeNewProjectRecovery();
        void navigate(`/app/projects/${project.id}`, { replace: true });
      } catch (reason) {
        const errorMessage =
          reason instanceof Error ? reason.message : "项目没有创建完成，请稍后重试";
        setMessage(errorMessage);
        patchRecovery({ errorMessage });
        setStage("idle");
      }
      return;
    }
    if (!file) {
      setMessage("请选择一份 PDF 教材");
      return;
    }
    if (file.type !== "application/pdf") {
      setMessage("目前只支持 PDF 教材");
      return;
    }

    const snapshot = fileSnapshot(file);
    let current = recoveryRef.current;
    const refreshed = refreshExpiredRuntimeUploadSession(current);
    if (refreshed !== current) current = replaceRecovery(refreshed);
    const fingerprint = runtimeNewProjectFingerprint(form, snapshot);
    if (!sameFileSnapshot(current.file, snapshot) || current.fingerprint !== fingerprint) {
      current = replaceRecovery(withNewRuntimeNewProjectIntent(form, snapshot));
    } else {
      current = patchRecovery({ form, errorMessage: undefined });
    }

    setMessage("");
    try {
      current = setSubmitStage("checking");
      const sha256 = await sha256File(file);
      // Same metadata with different content is a different intent. Do not
      // attach a new digest to an old project or upload session.
      if (current.file?.sha256 && current.file.sha256 !== sha256) {
        current = replaceRecovery(withNewRuntimeNewProjectIntent(form, { ...snapshot, sha256 }));
        current = setSubmitStage("checking");
      } else {
        current = patchRecovery({ file: { ...snapshot, sha256 } });
      }

      const refreshedRecovery = refreshExpiredRuntimeUploadSession(current);
      if (refreshedRecovery !== current) {
        current = replaceRecovery(refreshedRecovery);
      }

      let projectId = current.projectId;
      if (!projectId) {
        current = setSubmitStage("creating");
        const project = await createProject({
          idempotencyKey: current.intent.project,
          input: {
            execution_mode: values.executionMode,
            grade: values.grade,
            knowledge_point: values.knowledgePoint,
            textbook_edition: values.textbookEdition,
            title: values.title,
          },
        });
        projectId = project.id;
        current = patchRecovery({ projectId });
      }

      let session: UploadSessionDto | undefined = current.uploadSession;
      if (!session) {
        current = setSubmitStage("uploading");
        session = await createMaterialUploadSession({
          idempotencyKey: current.intent.upload,
          input: {
            filename: file.name,
            media_type: file.type,
            sha256,
            size_bytes: file.size,
          },
          projectId,
        });
        current = patchRecovery({ uploadSession: session });
      }

      let etag = current.etag;
      if (!etag) {
        current = setSubmitStage("uploading");
        etag = await uploadMaterialFile(session, file);
        current = patchRecovery({ etag });
      }

      current = setSubmitStage("confirming");
      const job = await confirmMaterialUpload({
        etag,
        file,
        idempotencyKey: current.intent.confirm,
        materialId: session.material_id,
        projectId,
        sha256,
        uploadSessionId: session.upload_session_id,
      });
      current = patchRecovery({ jobId: job.job_id, stage: "confirming" });
      await queryClient.invalidateQueries({ queryKey: projectKeys.all });
      void navigate(
        "/app/projects/" + projectId + "/setup?jobId=" + encodeURIComponent(job.job_id),
        { replace: true },
      );
    } catch (reason) {
      const errorMessage =
        reason instanceof Error ? reason.message : "项目没有创建完成，请稍后重试";
      setMessage(errorMessage);
      patchRecovery({ errorMessage });
      setStage("idle");
    }
  });

  const hasPendingProject = Boolean(recovery.projectId);
  const canContinueJob = Boolean(recovery.projectId && recovery.jobId);
  const writeReady = isCsrfTokenAvailable();
  const submitting = stage !== "idle";
  const formValues = watch();
  const sourceMode = formValues.sourceMode;
  const anchorSummary = `${formValues.grade} · ${formValues.textbookEdition} · ${formValues.knowledgePoint || "待填写知识点"}`;
  const setField = (field: ProjectEntryField, value: string) => {
    setValue(field, value, {
      shouldDirty: true,
      shouldValidate: true,
    });
  };
  const entryValues: ProjectEntryValues = {
    executionMode: formValues.executionMode,
    grade: formValues.grade,
    knowledgePoint: formValues.knowledgePoint,
    textbookEdition: formValues.textbookEdition,
    title: formValues.title,
  };

  return (
    <ProjectEntryFrame
      disabled={submitting}
      onSourceModeChange={(mode) =>
        setValue("sourceMode", mode, { shouldDirty: true, shouldValidate: true })
      }
      sourceMode={sourceMode}
    >
      {hasPendingProject ? (
        <section
          aria-label="已保存的课程进度"
          className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--sh-radius-md)] border border-[var(--sh-brand-200)] bg-[var(--sh-brand-50)] px-4 py-3"
          role="status"
        >
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--sh-brand-800)]">这份课程已经开始建立</p>
            <p className="mt-1 text-xs leading-5 text-[var(--sh-brand-700)]">
              {canContinueJob
                ? "教材解析任务已经建立，可以直接查看进度。"
                : stageDescription(recovery.stage)}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            {canContinueJob ? (
              <Button asChild className="min-h-9" size="sm" variant="secondary">
                <Link
                  to={`/app/projects/${recovery.projectId ?? ""}/setup?jobId=${encodeURIComponent(recovery.jobId ?? "")}`}
                >
                  继续查看进度
                </Link>
              </Button>
            ) : null}
            <Button disabled={submitting} onClick={resetDraft} size="sm" variant="quiet">
              重新开始
            </Button>
          </div>
        </section>
      ) : recovery.file ? (
        <p className="mt-4 rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] px-4 py-3 text-sm text-[var(--sh-ink-muted)]">
          已记住“{recovery.file.name}”的课程信息。刷新后浏览器不会保留文件本身，请重新选择同一份 PDF
          再继续。
        </p>
      ) : null}

      <ProjectEntryForm
        anchorSummary={anchorSummary}
        busy={submitting}
        errors={{
          knowledgePoint: errors.knowledgePoint?.message,
          title: errors.title?.message,
        }}
        file={file}
        message={message || (!writeReady ? "暂时无法保存，请刷新页面后重试。" : "")}
        modeOptions={modeOptions}
        onFieldChange={setField}
        onFileChange={selectFile}
        onSubmit={(event) => void submit(event)}
        recoveredFileName={recovery.file?.name}
        sourceMode={sourceMode}
        submitDisabled={!writeReady || (sourceMode === "textbook" && !file)}
        submitLabel={
          stage === "idle" && sourceMode === "anchor" ? "创建课程项目" : stageLabels[stage]
        }
        values={entryValues}
      />
    </ProjectEntryFrame>
  );
}
