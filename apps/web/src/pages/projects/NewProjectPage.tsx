import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { createProject } from "@/features/projects/api/projectsApi";
import {
  ProjectEntryForm,
  type ProjectEntryField,
} from "@/features/projects/components/ProjectEntryForm";
import { ProjectEntryFrame } from "@/features/projects/components/ProjectEntryFrame";
import { projectKeys } from "@/features/projects/hooks/useProjectsQuery";
import { apiConfig } from "@/shared/api/config";
import { addMockTextbookFile } from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";

const projectSchema = z.object({
  title: z.string().min(2, "请输入项目名称"),
  knowledgePoint: z.string().min(2, "请输入本次要制作的知识点"),
  sourceMode: z.enum(["textbook", "anchor"]),
  grade: z.string().min(1, "请选择年级"),
  textbookEdition: z.string().min(1, "请选择教材版本"),
  automationMode: z.enum(["manual", "assisted", "automatic"]),
});

type ProjectForm = z.infer<typeof projectSchema>;

const modeOptions = [
  { detail: "每一步都由你开始", label: "每步确认", value: "manual" },
  { detail: "系统准备，你来确认", label: "系统先准备", value: "assisted" },
  { detail: "可随时暂停并回来检查", label: "自动推进", value: "automatic" },
] as const;

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
    formState: { errors, isSubmitting },
    handleSubmit,
    setValue,
    watch,
  } = useForm<ProjectForm>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      automationMode: "assisted",
      grade: "六年级",
      knowledgePoint: "",
      sourceMode: "textbook",
      textbookEdition: "人教版",
      title: "",
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
    if (values.sourceMode === "textbook" && !file) {
      setFileError("请选择教材 PDF");
      return;
    }
    if (apiConfig.mode !== "mock") {
      setFileError("教材上传暂时不可用，你填写的内容不会提交。请稍后再试。");
      return;
    }
    const input = {
      automation_mode: values.automationMode,
      grade: values.grade,
      knowledge_point: values.knowledgePoint,
      textbook_edition: values.textbookEdition,
      title: values.title,
    };
    const fingerprint = JSON.stringify({
      file: file ? [file.name, file.size, file.lastModified] : null,
      input,
      sourceMode: values.sourceMode,
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
    if (file && values.sourceMode === "textbook") {
      addMockTextbookFile(project.id, {
        lastModified: file.lastModified,
        name: file.name,
        size: file.size,
        type: file.type,
      });
    }
    await queryClient.invalidateQueries({ queryKey: projectKeys.all });
    await navigate(
      values.sourceMode === "textbook"
        ? `/app/projects/${project.id}/materials`
        : `/app/projects/${project.id}`,
    );
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

  const values = watch();
  const busy = isSubmitting || createProjectMutation.isPending;
  const setField = (field: ProjectEntryField, value: string) => {
    switch (field) {
      case "executionMode":
        setValue("automationMode", value as ProjectForm["automationMode"], {
          shouldDirty: true,
          shouldValidate: true,
        });
        break;
      case "grade":
      case "knowledgePoint":
      case "textbookEdition":
      case "title":
        setValue(field, value, { shouldDirty: true, shouldValidate: true });
        break;
    }
  };

  return (
    <ProjectEntryFrame
      disabled={busy}
      eyebrow="新项目"
      onSourceModeChange={(mode) => {
        setValue("sourceMode", mode, { shouldDirty: true, shouldValidate: true });
        if (mode === "anchor") setFileError("");
      }}
      sourceMode={values.sourceMode}
    >
      {createProjectMutation.isError ? (
        <div className="mt-5 rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] p-4 text-sm text-[var(--sh-danger)]">
          项目暂时无法创建，已保留你填写的内容。请检查网络后重试。
        </div>
      ) : null}
      <ProjectEntryForm
        anchorSummary={`${values.grade} · ${values.textbookEdition} · ${values.knowledgePoint || "待填写知识点"}`}
        busy={busy}
        disabled={apiConfig.mode !== "mock"}
        errors={{
          knowledgePoint: errors.knowledgePoint?.message,
          title: errors.title?.message,
        }}
        file={file}
        fileError={fileError}
        modeOptions={modeOptions}
        onFieldChange={setField}
        onFileChange={selectFile}
        onSubmit={(event) => void submit(event)}
        sourceMode={values.sourceMode}
        submitDisabled={values.sourceMode === "textbook" && !file}
        submitLabel={values.sourceMode === "textbook" ? "创建项目并检查教材" : "创建课程项目"}
        uploadSectionRef={uploadStepRef}
        values={{
          executionMode: values.automationMode,
          grade: values.grade,
          knowledgePoint: values.knowledgePoint,
          textbookEdition: values.textbookEdition,
          title: values.title,
        }}
      />
      {values.sourceMode === "textbook" && !uploadStepVisible ? (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)]/95 px-3 pb-[calc(12px+env(safe-area-inset-bottom))] pt-3 shadow-[var(--sh-shadow-floating)] backdrop-blur-lg lg:hidden">
          <Button
            className="mx-auto flex w-full max-w-sm"
            onClick={() => uploadStepRef.current?.scrollIntoView({ block: "start" })}
          >
            下一步：上传教材
          </Button>
        </div>
      ) : null}
    </ProjectEntryFrame>
  );
}
