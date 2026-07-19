import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, FileText, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Controller, useForm } from "react-hook-form";
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
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { Select } from "@/shared/ui/Select";
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
  textbookEdition: z.string().min(1, "请选择教材版本"),
  title: z.string().min(2, "请输入项目名称"),
});

type ProjectForm = z.infer<typeof projectSchema>;
type SubmitStage = RuntimeNewProjectStage;

const stageLabels: Record<SubmitStage, string> = {
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
      return "教材已经传输，正在等待服务端建立解析任务。";
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
    control,
    formState: { errors },
    getValues,
    handleSubmit,
    register,
    reset,
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
      const fingerprint = current.file
        ? runtimeNewProjectFingerprint(form, current.file)
        : current.fingerprint;
      if (current.projectId && current.fingerprint && fingerprint !== current.fingerprint) {
        replaceRecovery(withNewRuntimeNewProjectIntent(form, current.file));
        return;
      }
      patchRecovery({ form, fingerprint });
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
    if (!file) {
      setMessage("请选择一份 PDF 教材");
      return;
    }
    if (file.type !== "application/pdf") {
      setMessage("目前只支持 PDF 教材");
      return;
    }

    const snapshot = fileSnapshot(file);
    const form = normalizeForm(values);
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

  const inputClass =
    "mt-1.5 min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3 text-sm text-[var(--sh-ink-strong)] outline-none transition focus:border-[var(--sh-brand-400)] focus:shadow-[var(--sh-shadow-focus)]";
  const hasPendingProject = Boolean(recovery.projectId);
  const canContinueJob = Boolean(recovery.projectId && recovery.jobId);
  const writeReady = isCsrfTokenAvailable();
  const submitting = stage !== "idle";

  return (
    <div className="mx-auto max-w-[1120px] px-4 py-5 md:px-6 lg:px-8">
      <FocusPageHeader
        description="填写课程信息并上传教材。系统会保存真实进度，刷新页面后也能继续查看。"
        title="新建课堂项目"
      />

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

      <form
        aria-busy={submitting}
        className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]"
        onSubmit={(event) => void submit(event)}
      >
        <section className="rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-card)]">
          <div className="flex items-center gap-2 text-[var(--sh-brand-700)]">
            <BookOpen aria-hidden="true" className="size-5" />
            <h2 className="font-semibold">这节课讲什么</h2>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-[var(--sh-ink-default)]">
              项目名称
              <input
                className={inputClass}
                disabled={submitting}
                {...register("title")}
                placeholder="例如：认识百分数"
              />
              {errors.title ? (
                <span className="mt-1 block text-xs text-[var(--sh-danger)]">
                  {errors.title.message}
                </span>
              ) : null}
            </label>
            <label className="text-sm font-medium text-[var(--sh-ink-default)]">
              知识点
              <input
                className={inputClass}
                disabled={submitting}
                {...register("knowledgePoint")}
                placeholder="例如：百分数的意义"
              />
              {errors.knowledgePoint ? (
                <span className="mt-1 block text-xs text-[var(--sh-danger)]">
                  {errors.knowledgePoint.message}
                </span>
              ) : null}
            </label>
            <Controller
              control={control}
              name="grade"
              render={({ field }) => (
                <label className="text-sm font-medium text-[var(--sh-ink-default)]">
                  年级
                  <Select
                    ariaLabel="选择年级"
                    className="mt-1.5 w-full"
                    disabled={submitting}
                    onValueChange={field.onChange}
                    options={["一年级", "二年级", "三年级", "四年级", "五年级", "六年级"].map(
                      (value) => ({ label: value, value }),
                    )}
                    value={field.value}
                  />
                </label>
              )}
            />
            <Controller
              control={control}
              name="textbookEdition"
              render={({ field }) => (
                <label className="text-sm font-medium text-[var(--sh-ink-default)]">
                  教材版本
                  <Select
                    ariaLabel="选择教材版本"
                    className="mt-1.5 w-full"
                    disabled={submitting}
                    onValueChange={field.onChange}
                    options={["人教版", "北师大版", "苏教版"].map((value) => ({
                      label: value,
                      value,
                    }))}
                    value={field.value}
                  />
                </label>
              )}
            />
          </div>
          <div className="mt-4">
            <p className="text-sm font-medium text-[var(--sh-ink-default)]">制作方式</p>
            <Controller
              control={control}
              name="executionMode"
              render={({ field }) => (
                <Select
                  ariaLabel="选择制作方式"
                  className="mt-1.5 w-full sm:w-72"
                  disabled={submitting}
                  onValueChange={field.onChange}
                  options={[
                    { label: "边看边确认", value: "guided" },
                    { label: "自动完成可执行步骤", value: "automatic" },
                  ]}
                  value={field.value}
                />
              )}
            />
          </div>
        </section>

        <section className="rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-card)]">
          <div className="flex items-center gap-2 text-[var(--sh-brand-700)]">
            <FileText aria-hidden="true" className="size-5" />
            <h2 className="font-semibold">上传教材</h2>
          </div>
          <label className="mt-4 grid min-h-40 cursor-pointer place-items-center rounded-[var(--sh-radius-md)] border border-dashed border-[var(--sh-brand-300)] bg-[var(--sh-brand-50)] p-5 text-center hover:border-[var(--sh-brand-500)]">
            <input
              accept="application/pdf"
              className="sr-only"
              disabled={submitting}
              onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
              type="file"
            />
            <span>
              <Upload aria-hidden="true" className="mx-auto size-7 text-[var(--sh-brand-600)]" />
              <span className="mt-2 block text-sm font-semibold text-[var(--sh-ink-strong)]">
                {file?.name ?? (recovery.file?.name ? "重新选择同一份 PDF" : "选择 PDF 教材")}
              </span>
              <span className="mt-1 block text-xs text-[var(--sh-ink-muted)]">
                {file ? (file.size / 1024 / 1024).toFixed(1) + " MB" : "文件会直接上传到受控存储"}
              </span>
            </span>
          </label>
          {message ? (
            <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
              {message}
            </p>
          ) : null}
          <Button className="mt-4 w-full" disabled={submitting || !writeReady} type="submit">
            {stage === "idle" ? <Upload aria-hidden="true" /> : null}
            {stageLabels[stage]}
          </Button>
          {!writeReady ? (
            <p className="mt-3 text-xs leading-5 text-[var(--sh-warning)]" role="status">
              安全会话尚未就绪，请刷新后重试。
            </p>
          ) : null}
          <p className="mt-3 text-xs leading-5 text-[var(--sh-ink-faint)]">
            上传完成后会进入教材解析。页面只展示服务端返回的真实状态。
          </p>
        </section>
      </form>
    </div>
  );
}
