import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, FileText, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import {
  confirmMaterialUpload,
  createMaterialUploadSession,
  sha256File,
  uploadMaterialFile,
} from "@/features/materials/api/materialsApi";
import { createProject } from "@/features/projects/api/projectsApi";
import { projectKeys } from "@/features/projects/hooks/useProjectsQuery";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { Select } from "@/shared/ui/Select";

const projectSchema = z.object({
  executionMode: z.enum(["guided", "automatic"]),
  grade: z.string().min(1, "请选择年级"),
  knowledgePoint: z.string().min(2, "请输入本次要制作的知识点"),
  textbookEdition: z.string().min(1, "请选择教材版本"),
  title: z.string().min(2, "请输入项目名称"),
});

type ProjectForm = z.infer<typeof projectSchema>;
type SubmitStage = "idle" | "checking" | "creating" | "uploading" | "confirming";

const stageLabels: Record<SubmitStage, string> = {
  checking: "正在核对教材",
  confirming: "正在建立课堂任务",
  creating: "正在创建课程",
  idle: "创建项目并上传教材",
  uploading: "正在上传教材",
};

export function RuntimeNewProjectPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [stage, setStage] = useState<SubmitStage>("idle");
  const intent = useRef({
    confirm: crypto.randomUUID(),
    fingerprint: "",
    project: crypto.randomUUID(),
    upload: crypto.randomUUID(),
  });
  const {
    control,
    formState: { errors },
    handleSubmit,
    register,
  } = useForm<ProjectForm>({
    defaultValues: {
      executionMode: "guided",
      grade: "六年级",
      textbookEdition: "人教版",
    },
    resolver: zodResolver(projectSchema),
  });

  const submit = handleSubmit(async (values) => {
    if (!file) {
      setMessage("请选择一份 PDF 教材");
      return;
    }
    if (file.type !== "application/pdf") {
      setMessage("目前只支持 PDF 教材");
      return;
    }
    const fingerprint = JSON.stringify([values, file.name, file.size, file.lastModified]);
    if (fingerprint !== intent.current.fingerprint) {
      intent.current = {
        confirm: crypto.randomUUID(),
        fingerprint,
        project: crypto.randomUUID(),
        upload: crypto.randomUUID(),
      };
    }

    setMessage("");
    try {
      setStage("checking");
      const sha256 = await sha256File(file);
      setStage("creating");
      const project = await createProject({
        idempotencyKey: intent.current.project,
        input: {
          execution_mode: values.executionMode,
          grade: values.grade,
          knowledge_point: values.knowledgePoint,
          textbook_edition: values.textbookEdition,
          title: values.title,
        },
      });
      const session = await createMaterialUploadSession({
        idempotencyKey: intent.current.upload,
        input: {
          filename: file.name,
          media_type: file.type,
          sha256,
          size_bytes: file.size,
        },
        projectId: project.id,
      });
      setStage("uploading");
      const etag = await uploadMaterialFile(session, file);
      setStage("confirming");
      const job = await confirmMaterialUpload({
        etag,
        file,
        idempotencyKey: intent.current.confirm,
        materialId: session.material_id,
        projectId: project.id,
        sha256,
        uploadSessionId: session.upload_session_id,
      });
      await queryClient.invalidateQueries({ queryKey: projectKeys.all });
      void navigate(
        "/app/projects/" + project.id + "/setup?jobId=" + encodeURIComponent(job.job_id),
        { replace: true },
      );
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "项目没有创建完成，请稍后重试");
      setStage("idle");
    }
  });

  const inputClass =
    "mt-1.5 min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3 text-sm text-[var(--sh-ink-strong)] outline-none transition focus:border-[var(--sh-brand-400)] focus:shadow-[var(--sh-shadow-focus)]";
  return (
    <div className="mx-auto max-w-[1120px] px-4 py-5 md:px-6 lg:px-8">
      <FocusPageHeader
        description="填写课程信息并上传教材。系统会保存真实进度，刷新页面后也能继续查看。"
        title="新建课堂项目"
      />
      <form
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
              <input className={inputClass} {...register("title")} placeholder="例如：认识百分数" />
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
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setMessage("");
              }}
              type="file"
            />
            <span>
              <Upload aria-hidden="true" className="mx-auto size-7 text-[var(--sh-brand-600)]" />
              <span className="mt-2 block text-sm font-semibold text-[var(--sh-ink-strong)]">
                {file?.name ?? "选择 PDF 教材"}
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
          <Button className="mt-4 w-full" disabled={stage !== "idle"} type="submit">
            {stage === "idle" ? <Upload aria-hidden="true" /> : null}
            {stageLabels[stage]}
          </Button>
          <p className="mt-3 text-xs leading-5 text-[var(--sh-ink-faint)]">
            上传完成后会进入教材解析。页面只展示服务端返回的真实状态。
          </p>
        </section>
      </form>
    </div>
  );
}
