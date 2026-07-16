import { useState } from "react";
import { useNavigate } from "react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, ArrowRight, CheckCircle2, FileText } from "lucide-react";
import { useCreateProject, useUpdateProject } from "@/features/projects";
import { useUploadSource, type UploadResult } from "@/features/uploads";
import type { Project } from "@/shared/api/types";
import { formatFileSize } from "@/shared/lib/format";
import { cn } from "@/shared/lib/cn";
import {
  Button,
  FormField,
  Input,
  PageHeader,
  RadioGroup,
  RadioGroupItem,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
  toast,
} from "@/shared/ui";
import { AppErrorPanel, UploadDropzone } from "@/widgets";

const basicSchema = z.object({
  name: z.string().min(2, "项目名称至少 2 个字").max(50, "项目名称不超过 50 个字"),
  grade: z.coerce.number().int().min(1).max(6),
  textbook_version: z.string().min(1, "请选择教材版本"),
  volume: z.string().min(1, "请选择册次"),
  execution_mode: z.enum(["manual", "semi_auto", "full_auto_draft"]),
});

type BasicForm = z.infer<typeof basicSchema>;

const STEPS = ["基本信息", "教材（可选）", "输出与预算"];

const MODE_OPTIONS = [
  { value: "manual", label: "手动模式", description: "每一步都由你发起并审核，最可控。" },
  { value: "semi_auto", label: "半自动模式", description: "系统自动推进免费步骤，付费生成和审核仍由你确认。" },
  { value: "full_auto_draft", label: "全自动草稿模式", description: "自动生成全链路草稿，最后统一审核；费用消耗较快。" },
] as const;

export function ProjectCreatePage() {
  const navigate = useNavigate();
  const createProject = useCreateProject();
  const [step, setStep] = useState(0);
  const [textbookFile, setTextbookFile] = useState<{ id: string; name: string; size: number } | null>(null);
  const [outputScope, setOutputScope] = useState({ ppt: true, video: true });
  const [budgetYuan, setBudgetYuan] = useState("300");

  const form = useForm<BasicForm>({
    resolver: zodResolver(basicSchema),
    defaultValues: { name: "", grade: 3, textbook_version: "人教版", volume: "上册", execution_mode: "semi_auto" },
    mode: "onTouched",
  });

  // 教材上传需要项目上下文：向导内先创建草稿项目再直传
  const [draftProject, setDraftProject] = useState<Project | null>(null);
  const upload = useUploadSource(draftProject?.project_id ?? "");
  const updateProject = useUpdateProject(draftProject?.project_id ?? "");

  const goStep2 = form.handleSubmit(async (values) => {
    if (!draftProject) {
      const project = await createProject.mutateAsync({
        ...values,
        budget_minor_units: Math.round(Number(budgetYuan) * 100) || 0,
        output_scope: outputScope,
      });
      setDraftProject(project);
    }
    setStep(1);
  });

  const finish = async () => {
    if (!draftProject) return;
    // 第三步的调整（输出范围/预算）落库
    await updateProject.mutateAsync({
      output_scope: outputScope,
      budget_minor_units: Math.round(Number(budgetYuan) * 100) || 0,
      row_version: draftProject.row_version,
    });
    toast({ tone: "success", title: "项目创建成功", description: textbookFile ? "教材解析已在后台进行。" : undefined });
    await navigate(`/app/projects/${draftProject.project_id}`);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <PageHeader title="新建项目" description="三步完成：基本信息 → 上传教材 → 输出与预算。" />

      <ol className="flex items-center gap-2" aria-label="创建步骤">
        {STEPS.map((label, index) => (
          <li key={label} className="flex flex-1 items-center gap-2">
            <span
              className={cn(
                "flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                index < step ? "bg-success text-white" : index === step ? "bg-brand text-white" : "bg-surface-2 text-ink-muted",
              )}
            >
              {index < step ? <CheckCircle2 className="size-4" aria-hidden /> : index + 1}
            </span>
            <span className={cn("text-sm", index === step ? "font-medium text-ink-1" : "text-ink-muted")}>{label}</span>
            {index < STEPS.length - 1 ? <span className="h-px flex-1 bg-line" aria-hidden /> : null}
          </li>
        ))}
      </ol>

      <div className="rounded-panel border border-line bg-surface-1 p-6">
        {step === 0 ? (
          <form className="space-y-4" onSubmit={(event) => void goStep2(event)} noValidate>
            <FormField label="项目名称" required error={form.formState.errors.name?.message}>
              {({ id, describedBy }) => (
                <Input id={id} aria-describedby={describedBy} placeholder="例如：三年级上册·分数的初步认识" {...form.register("name")} />
              )}
            </FormField>
            <div className="grid grid-cols-3 gap-3">
              <FormField label="年级" required error={form.formState.errors.grade?.message}>
                {({ id }) => (
                  <Select value={String(form.watch("grade"))} onValueChange={(value) => form.setValue("grade", Number(value))}>
                    <SelectTrigger id={id}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 4, 5, 6].map((grade) => (
                        <SelectItem key={grade} value={String(grade)}>
                          {grade}年级
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </FormField>
              <FormField label="教材版本" required error={form.formState.errors.textbook_version?.message}>
                {({ id }) => (
                  <Select value={form.watch("textbook_version")} onValueChange={(value) => form.setValue("textbook_version", value)}>
                    <SelectTrigger id={id}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["人教版", "北师大版", "苏教版"].map((version) => (
                        <SelectItem key={version} value={version}>
                          {version}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </FormField>
              <FormField label="册次" required error={form.formState.errors.volume?.message}>
                {({ id }) => (
                  <Select value={form.watch("volume")} onValueChange={(value) => form.setValue("volume", value)}>
                    <SelectTrigger id={id}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="上册">上册</SelectItem>
                      <SelectItem value="下册">下册</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              </FormField>
            </div>
            <FormField label="执行模式" required description="创建后可在项目设置中调整。">
              {() => (
                <RadioGroup
                  value={form.watch("execution_mode")}
                  onValueChange={(value) => form.setValue("execution_mode", value as BasicForm["execution_mode"])}
                  className="space-y-2"
                >
                  {MODE_OPTIONS.map((option) => (
                    <label
                      key={option.value}
                      className={cn(
                        "flex cursor-pointer items-start gap-3 rounded-control border px-4 py-3 transition-colors",
                        form.watch("execution_mode") === option.value ? "border-brand bg-brand-selected" : "border-line hover:bg-surface-hover",
                      )}
                    >
                      <RadioGroupItem value={option.value} className="mt-0.5" />
                      <span>
                        <span className="block text-sm font-medium text-ink-1">{option.label}</span>
                        <span className="block text-xs text-ink-2">{option.description}</span>
                      </span>
                    </label>
                  ))}
                </RadioGroup>
              )}
            </FormField>
            {createProject.isError ? <AppErrorPanel error={createProject.error} title="项目创建失败" /> : null}
            <div className="flex justify-end">
              <Button type="submit" loading={createProject.isPending}>
                下一步
                <ArrowRight className="size-4" aria-hidden />
              </Button>
            </div>
          </form>
        ) : step === 1 ? (
          <div className="space-y-4">
            <p className="text-sm text-ink-2">上传教材 PDF 后，系统会自动解析出教材证据（目录、知识点、页码对照），供课时划分使用。也可以先跳过。</p>
            {textbookFile ? (
              <div className="flex items-center gap-3 rounded-control border border-line bg-surface-2 px-4 py-3">
                <FileText className="size-5 text-brand" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink-1">{textbookFile.name}</p>
                  <p className="text-xs text-ink-muted">{formatFileSize(textbookFile.size)} · 已上传，解析任务已启动</p>
                </div>
                <CheckCircle2 className="size-5 text-success" aria-hidden />
              </div>
            ) : (
              <UploadDropzone
                accept=".pdf"
                maxSizeBytes={200 * 1024 * 1024}
                uploading={upload.isPending}
                onFile={(file) => {
                  upload.mutate(
                    { file, sourceType: "textbook" },
                    {
                      onSuccess: (result: UploadResult) => {
                        setTextbookFile({ id: result.fileObject.file_object_id, name: file.name, size: file.size });
                      },
                    },
                  );
                }}
              />
            )}
            {upload.isError ? <AppErrorPanel error={upload.error} title="教材上传失败" /> : null}
            <div className="flex justify-between">
              <Button variant="ghost" onClick={() => setStep(0)}>
                <ArrowLeft className="size-4" aria-hidden />
                上一步
              </Button>
              <Button onClick={() => setStep(2)}>
                {textbookFile ? "下一步" : "跳过，稍后上传"}
                <ArrowRight className="size-4" aria-hidden />
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <FormField label="输出内容" description="不勾选的链路会在工作台中标记为「跳过」，之后可以恢复。">
              {() => (
                <div className="space-y-2">
                  <label className="flex items-center justify-between rounded-control border border-line px-4 py-3">
                    <span className="text-sm text-ink-1">课件 PPT</span>
                    <Switch checked={outputScope.ppt} onCheckedChange={(checked) => setOutputScope((prev) => ({ ...prev, ppt: checked }))} />
                  </label>
                  <label className="flex items-center justify-between rounded-control border border-line px-4 py-3">
                    <span className="text-sm text-ink-1">导入视频</span>
                    <Switch
                      checked={outputScope.video}
                      onCheckedChange={(checked) => setOutputScope((prev) => ({ ...prev, video: checked }))}
                    />
                  </label>
                </div>
              )}
            </FormField>
            <FormField label="项目预算（元）" description="模型调用累计费用达到预算时，需要额外授权才能继续付费生成。">
              {({ id, describedBy }) => (
                <Input
                  id={id}
                  aria-describedby={describedBy}
                  type="number"
                  min={0}
                  step={10}
                  value={budgetYuan}
                  onChange={(event) => setBudgetYuan(event.target.value)}
                  className="w-40"
                />
              )}
            </FormField>
            {updateProject.isError ? <AppErrorPanel error={updateProject.error} title="保存失败" /> : null}
            <div className="flex justify-between">
              <Button variant="ghost" onClick={() => setStep(1)}>
                <ArrowLeft className="size-4" aria-hidden />
                上一步
              </Button>
              <Button onClick={() => void finish()} loading={updateProject.isPending}>
                完成创建，进入项目
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
