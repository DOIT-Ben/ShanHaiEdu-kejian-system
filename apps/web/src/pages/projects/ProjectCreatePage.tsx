import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { ArrowLeft } from "lucide-react";
import { useCreateProject } from "@/features/projects";
import { AppError } from "@/shared/api";
import { Button, FormField, Input, PageHeader, RadioGroup, RadioGroupItem, toast } from "@/shared/ui";

const MODES = [
  {
    value: "manual" as const,
    title: "手动模式",
    description: "每一步都由你启动和确认，适合第一次使用或要求精细控制。",
  },
  {
    value: "assisted" as const,
    title: "半自动模式（推荐）",
    description: "系统自动推进能确定的步骤，在需要判断的地方等你确认。",
  },
  {
    value: "automatic" as const,
    title: "全自动模式",
    description: "系统按预算自动完成全部步骤，超出预算或遇到问题时暂停等你。",
  },
];

/** 新建项目：填写知识点信息 → 创建后进入教材上传。 */
export default function ProjectCreatePage() {
  const navigate = useNavigate();
  const createProject = useCreateProject();
  const [title, setTitle] = useState("");
  const [knowledgePoint, setKnowledgePoint] = useState("");
  const [grade, setGrade] = useState("");
  const [edition, setEdition] = useState("");
  const [mode, setMode] = useState<"manual" | "assisted" | "automatic">("assisted");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const errors: Record<string, string> = {};
    if (!title.trim()) errors.title = "请输入项目名称";
    if (!knowledgePoint.trim()) errors.knowledge_point = "请输入本项目的知识点";
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;
    createProject.mutate(
      {
        title: title.trim(),
        knowledge_point: knowledgePoint.trim(),
        ...(grade.trim() ? { grade: grade.trim() } : {}),
        ...(edition.trim() ? { textbook_edition: edition.trim() } : {}),
        automation_mode: mode,
      },
      {
        onSuccess: (project) => {
          toast({ tone: "success", title: "项目已创建", description: "下一步：上传教材。" });
          void navigate(`/app/projects/${project.id}/materials`);
        },
        onError: (error) => {
          if (error instanceof AppError) {
            setFieldErrors(error.fieldErrors());
            toast({ tone: "danger", title: "创建失败", description: error.message });
          }
        },
      },
    );
  };

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-8">
      <Button variant="ghost" size="sm" onClick={() => void navigate(-1)} className="-ml-2 mb-4">
        <ArrowLeft className="size-4" aria-hidden />
        返回
      </Button>
      <PageHeader
        title="创建项目"
        description="一个项目围绕一个知识点。创建后上传教材，系统会给出课时划分建议。"
      />
      <form onSubmit={submit} className="mt-8 space-y-6" noValidate>
        <FormField label="项目名称" required error={fieldErrors.title}>
          {({ id, describedBy }) => (
            <Input
              id={id}
              value={title}
              aria-describedby={describedBy}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：认识几分之几"
            />
          )}
        </FormField>
        <FormField label="知识点" required error={fieldErrors.knowledge_point} description="用教材上的说法，如“几分之几”“面积单位换算”。">
          {({ id, describedBy }) => (
            <Input
              id={id}
              value={knowledgePoint}
              aria-describedby={describedBy}
              onChange={(e) => setKnowledgePoint(e.target.value)}
              placeholder="例如：几分之几"
            />
          )}
        </FormField>
        <div className="grid gap-6 sm:grid-cols-2">
          <FormField label="年级（可选）">
            {({ id }) => (
              <Input id={id} value={grade} onChange={(e) => setGrade(e.target.value)} placeholder="例如：三年级上册" />
            )}
          </FormField>
          <FormField label="教材版本（可选）">
            {({ id }) => (
              <Input id={id} value={edition} onChange={(e) => setEdition(e.target.value)} placeholder="例如：人教版" />
            )}
          </FormField>
        </div>
        <fieldset>
          <legend className="text-sm font-medium text-ink-strong">创作方式</legend>
          <RadioGroup
            value={mode}
            onValueChange={(value) => setMode(value as typeof mode)}
            className="mt-3 space-y-3"
          >
            {MODES.map((item) => (
              <label
                key={item.value}
                className="flex cursor-pointer items-start gap-3 rounded-md border border-line-subtle bg-surface p-4 transition-colors duration-150 has-[[data-state=checked]]:border-brand-500 has-[[data-state=checked]]:bg-brand-50/50"
              >
                <RadioGroupItem value={item.value} className="mt-0.5" />
                <span>
                  <span className="block text-sm font-medium text-ink-strong">{item.title}</span>
                  <span className="mt-0.5 block text-sm leading-relaxed text-ink-muted">{item.description}</span>
                </span>
              </label>
            ))}
          </RadioGroup>
        </fieldset>
        <div className="flex items-center gap-3 pt-2">
          <Button type="submit" loading={createProject.isPending} loadingText="正在创建…">
            创建项目，去上传教材
          </Button>
          <Button type="button" variant="ghost" onClick={() => void navigate("/app/projects")}>
            取消
          </Button>
        </div>
      </form>
    </div>
  );
}
