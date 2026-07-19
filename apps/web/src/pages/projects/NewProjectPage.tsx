import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileText, Upload, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { createProject } from "@/features/projects/api/projectsApi";
import { projectKeys } from "@/features/projects/hooks/useProjectsQuery";
import { apiConfig } from "@/shared/api/config";
import { addMockTextbookFile } from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { Select } from "@/shared/ui/Select";

const projectSchema = z.object({
  title: z.string().min(2, "请输入项目名称"),
  knowledgePoint: z.string().min(2, "请输入本次要制作的知识点"),
  grade: z.string().min(1, "请选择年级"),
  textbookEdition: z.string().min(1, "请选择教材版本"),
  automationMode: z.enum(["manual", "assisted", "automatic"]),
});

type ProjectForm = z.infer<typeof projectSchema>;

export function NewProjectPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState("");
  const [uploadStepVisible, setUploadStepVisible] = useState(false);
  const uploadStepRef = useRef<HTMLElement>(null);
  const createIntentKey = useRef(crypto.randomUUID());
  const createIntentFingerprint = useRef("");
  const createProjectMutation = useMutation({ mutationFn: createProject });
  const {
    control,
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<ProjectForm>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      automationMode: "assisted",
      grade: "六年级",
      textbookEdition: "人教版",
    },
  });

  useEffect(() => {
    if (!("IntersectionObserver" in window) || !uploadStepRef.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => setUploadStepVisible(entry?.isIntersecting ?? false),
      { threshold: 0.25 },
    );
    observer.observe(uploadStepRef.current);
    return () => observer.disconnect();
  }, []);

  const submit = handleSubmit(async (values) => {
    if (!file) {
      setFileError("请选择教材 PDF");
      return;
    }
    if (apiConfig.mode !== "mock") {
      setFileError("教材上传暂时不可用，你填写的内容不会提交。请稍后再试。");
      return;
    }
    const input = {
      title: values.title,
      knowledge_point: values.knowledgePoint,
      grade: values.grade,
      textbook_edition: values.textbookEdition,
      automation_mode: values.automationMode,
    };
    const fingerprint = JSON.stringify({
      file: [file.name, file.size, file.lastModified],
      input,
    });
    if (fingerprint !== createIntentFingerprint.current) {
      createIntentFingerprint.current = fingerprint;
      createIntentKey.current = crypto.randomUUID();
    }
    let project;
    try {
      project = await createProjectMutation.mutateAsync({
        idempotencyKey: createIntentKey.current,
        input,
      });
    } catch {
      return;
    }
    createIntentKey.current = crypto.randomUUID();
    addMockTextbookFile(project.id, {
      name: file.name,
      size: file.size,
      type: file.type,
      lastModified: file.lastModified,
    });
    await queryClient.invalidateQueries({ queryKey: projectKeys.all });
    await navigate(`/app/projects/${project.id}/materials`);
  });

  const selectFile = (nextFile: File | null) => {
    if (!nextFile) {
      setFile(null);
      setFileError("");
      return;
    }
    if (nextFile.type !== "application/pdf" || !nextFile.name.toLowerCase().endsWith(".pdf")) {
      setFile(null);
      setFileError("只支持 PDF 教材文件");
      return;
    }
    if (nextFile.size > 100 * 1024 * 1024) {
      setFile(null);
      setFileError("教材文件不能超过 100 MB");
      return;
    }
    setFile(nextFile);
    setFileError("");
  };

  return (
    <div className="mx-auto max-w-5xl px-5 pb-24 pt-6 md:px-8 lg:pb-6">
      <FocusPageHeader
        description="上传一个小知识点的教材 PDF，系统会先检查文件和范围，再安排课时。"
        eyebrow="新项目"
        title="从教材开始一套课堂作品"
      />

      <ol
        aria-label="创建项目步骤"
        className="mt-5 grid grid-cols-2 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-1 lg:hidden"
      >
        <li className="rounded-lg bg-[var(--sh-surface-soft)] px-3 py-2 text-xs font-semibold text-[var(--sh-brand-700)]">
          1&nbsp; 填写项目信息
        </li>
        <li className="px-3 py-2 text-xs font-medium text-[var(--sh-ink-muted)]">
          2&nbsp; 上传教材
        </li>
      </ol>

      {createProjectMutation.isError ? (
        <div className="mt-6 rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] p-4 text-sm text-[var(--sh-danger)]">
          项目暂时无法创建，已保留你填写的内容。请检查网络后重试。
        </div>
      ) : null}

      <form
        className="mt-6 grid gap-5 lg:grid-cols-[1.15fr_0.85fr]"
        onSubmit={(event) => {
          void submit(event);
        }}
      >
        <section className="space-y-5 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 md:p-6">
          <div>
            <h2 className="text-lg font-semibold text-[var(--sh-ink-strong)]">项目信息</h2>
            <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
              先说明要讲什么，稍后仍可修改。
            </p>
          </div>

          <label className="block">
            <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">项目名称</span>
            <input
              aria-invalid={Boolean(errors.title)}
              className="mt-2 min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] px-3 outline-none focus:border-[var(--sh-brand-500)]"
              placeholder="例如：认识百分数"
              {...register("title")}
            />
            {errors.title ? (
              <span className="mt-1 block text-sm text-[var(--sh-danger)]">
                {errors.title.message}
              </span>
            ) : null}
          </label>

          <label className="block">
            <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">知识点</span>
            <input
              aria-invalid={Boolean(errors.knowledgePoint)}
              className="mt-2 min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] px-3 outline-none focus:border-[var(--sh-brand-500)]"
              placeholder="这份教材主要讲什么？"
              {...register("knowledgePoint")}
            />
            {errors.knowledgePoint ? (
              <span className="mt-1 block text-sm text-[var(--sh-danger)]">
                {errors.knowledgePoint.message}
              </span>
            ) : null}
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">年级</span>
              <Controller
                control={control}
                name="grade"
                render={({ field }) => (
                  <Select
                    ariaLabel="年级"
                    className="mt-2 w-full"
                    onBlur={field.onBlur}
                    onValueChange={field.onChange}
                    options={["一年级", "二年级", "三年级", "四年级", "五年级", "六年级"].map(
                      (grade) => ({ label: grade, value: grade }),
                    )}
                    value={field.value}
                  />
                )}
              />
            </label>
            <label className="block">
              <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">教材版本</span>
              <Controller
                control={control}
                name="textbookEdition"
                render={({ field }) => (
                  <Select
                    ariaLabel="教材版本"
                    className="mt-2 w-full"
                    onBlur={field.onBlur}
                    onValueChange={field.onChange}
                    options={["人教版", "北师大版", "苏教版", "冀教版"].map((edition) => ({
                      label: edition,
                      value: edition,
                    }))}
                    value={field.value}
                  />
                )}
              />
            </label>
          </div>

          <fieldset>
            <legend className="text-sm font-semibold text-[var(--sh-ink-strong)]">
              我想怎么推进
            </legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              {[
                ["manual", "每步确认", "每一步都由你开始"],
                ["assisted", "系统先准备", "推荐：系统准备，你来确认"],
                ["automatic", "自动推进", "可随时暂停并回来检查"],
              ].map(([value, label, detail]) => (
                <label
                  className="cursor-pointer rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] p-2.5 has-[:checked]:border-[var(--sh-brand-500)] has-[:checked]:bg-[var(--sh-brand-50)]"
                  key={value}
                >
                  <input
                    className="sr-only"
                    type="radio"
                    value={value}
                    {...register("automationMode")}
                  />
                  <span className="block text-sm font-semibold text-[var(--sh-ink-strong)]">
                    {label}
                  </span>
                  <span className="mt-1 block text-xs text-[var(--sh-ink-muted)]">{detail}</span>
                </label>
              ))}
            </div>
          </fieldset>
        </section>

        <section
          className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 md:p-6"
          id="textbook-upload-step"
          ref={uploadStepRef}
        >
          <h2 className="text-lg font-semibold text-[var(--sh-ink-strong)]">教材文件</h2>
          <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
            支持 PDF，建议只包含当前知识点的相关页。
          </p>

          {file ? (
            <div className="mt-6 rounded-[var(--sh-radius-sm)] border border-[var(--sh-success)] bg-[var(--sh-success-soft)] p-4">
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-md bg-[var(--sh-surface-elevated)] text-[var(--sh-success)]">
                  <FileText aria-hidden="true" className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-[var(--sh-ink-strong)]">
                    {file.name}
                  </p>
                  <p className="text-xs text-[var(--sh-ink-muted)]">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </p>
                </div>
                <button
                  aria-label="移除教材文件"
                  className="grid size-9 place-items-center rounded-md hover:bg-[var(--sh-surface-elevated)]"
                  onClick={() => selectFile(null)}
                  type="button"
                >
                  <X aria-hidden="true" className="size-4" />
                </button>
              </div>
              <p className="mt-4 flex items-center gap-2 text-xs text-[var(--sh-success)]">
                <CheckCircle2 aria-hidden="true" className="size-4" />
                文件将在创建项目后上传并检查
              </p>
            </div>
          ) : (
            <label
              className="mt-5 flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-[var(--sh-radius-sm)] border border-dashed border-[var(--sh-line-strong)] bg-[var(--sh-surface-soft)] px-6 text-center hover:border-[var(--sh-brand-300)] hover:bg-[var(--sh-brand-50)]"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                selectFile(event.dataTransfer.files[0] ?? null);
              }}
            >
              <span className="grid size-12 place-items-center rounded-full bg-[var(--sh-surface-elevated)] text-[var(--sh-brand-600)] shadow-sm">
                <Upload aria-hidden="true" className="size-5" />
              </span>
              <strong className="mt-4 text-sm text-[var(--sh-ink-strong)]">
                拖入或选择教材 PDF
              </strong>
              <span className="mt-1 text-xs text-[var(--sh-ink-muted)]">单个文件不超过 100 MB</span>
              <input
                aria-describedby={fileError ? "textbook-file-error" : undefined}
                accept="application/pdf"
                className="sr-only"
                onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>
          )}

          {fileError ? (
            <p
              className="mt-3 text-sm font-medium text-[var(--sh-danger)]"
              id="textbook-file-error"
              role="alert"
            >
              {fileError}
            </p>
          ) : null}

          <Button
            className="mt-6 w-full"
            disabled={
              apiConfig.mode !== "mock" || !file || isSubmitting || createProjectMutation.isPending
            }
            size="lg"
            type="submit"
          >
            {apiConfig.mode !== "mock"
              ? "教材上传暂时不可用"
              : isSubmitting || createProjectMutation.isPending
                ? "正在创建项目"
                : "创建项目并检查教材"}
          </Button>
          <p className="mt-3 text-center text-xs text-[var(--sh-ink-faint)]">
            {!file
              ? "请先选择教材 PDF；创建后仍可确认教材范围和课时。"
              : "创建后不会立即生成教案，你可以先确认教材范围和课时。"}
          </p>
        </section>
      </form>
      {!uploadStepVisible ? (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)]/95 px-3 pb-[calc(12px+env(safe-area-inset-bottom))] pt-3 shadow-[var(--sh-shadow-floating)] backdrop-blur-lg lg:hidden">
          <Button
            className="mx-auto flex w-full max-w-sm"
            onClick={() => uploadStepRef.current?.scrollIntoView({ block: "start" })}
          >
            下一步：上传教材
          </Button>
        </div>
      ) : null}
    </div>
  );
}
