import { AlertTriangle, CheckCircle2, GripVertical, Plus, Save } from "lucide-react";
import { useState } from "react";
import { getMockDraft, saveMockDraft } from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { Select } from "@/shared/ui/Select";

const WORKFLOW_DRAFT_KEY = "admin.workflow.editor";
const contextOptions = ["批准课时范围", "教材页码证据", "批准教案", "教师偏好"];

type WorkflowStep = {
  id: string;
  name: string;
  capability: string;
  confirmation: string;
  budget: string;
  retry: string;
  contexts: string[];
};

type WorkflowDefinition = { steps: WorkflowStep[] };
type PublishedWorkflowVersion = WorkflowDefinition & { version: number; publishedAt: string };
type WorkflowStore = {
  draft: WorkflowDefinition;
  publishedVersions: PublishedWorkflowVersion[];
};

type LegacyWorkflowDraft = {
  steps: string[];
  capability: string;
  confirmation: string;
  budget: string;
  retry: string;
  contexts: string[];
  publishedVersion: number;
};

const defaultStepNames = [
  "教材解析",
  "课时划分",
  "教案生成",
  "独立创意",
  "最小课程锚定",
  "PPT 制作",
  "导入视频制作",
  "项目交付",
];

function createStep(name: string, index: number): WorkflowStep {
  return {
    id: `step-${String(index + 1)}`,
    name,
    capability: "小学数学教案生成",
    confirmation: "强制确认",
    budget: "8.00",
    retry: "最多 2 次",
    contexts: ["批准课时范围", "教材页码证据", "教师偏好"],
  };
}

const defaultWorkflow: WorkflowStore = {
  draft: { steps: defaultStepNames.map(createStep) },
  publishedVersions: [],
};

function readWorkflowDraft() {
  const stored = getMockDraft(WORKFLOW_DRAFT_KEY)?.value;
  if (stored && typeof stored === "object") {
    const candidate = stored as Partial<WorkflowStore>;
    if (
      candidate.draft &&
      Array.isArray(candidate.draft.steps) &&
      Array.isArray(candidate.publishedVersions)
    ) {
      return candidate as WorkflowStore;
    }
    const legacy = stored as Partial<LegacyWorkflowDraft>;
    if (Array.isArray(legacy.steps) && legacy.steps.every((step) => typeof step === "string")) {
      const steps = legacy.steps.map((name, index) => ({
        ...createStep(name, index),
        capability: legacy.capability ?? "小学数学教案生成",
        confirmation: legacy.confirmation ?? "强制确认",
        budget: legacy.budget ?? "8.00",
        retry: legacy.retry ?? "最多 2 次",
        contexts: Array.isArray(legacy.contexts) ? legacy.contexts : [],
      }));
      const version = legacy.publishedVersion ?? 0;
      return {
        draft: { steps },
        publishedVersions:
          version > 0 ? [{ version, publishedAt: new Date(0).toISOString(), steps }] : [],
      };
    }
  }
  return defaultWorkflow;
}

export function AdminWorkflowsPage() {
  const [workflow, setWorkflow] = useState(readWorkflowDraft);
  const [selected, setSelected] = useState(() => Math.min(2, workflow.draft.steps.length - 1));
  const [checked, setChecked] = useState(false);
  const [saved, setSaved] = useState(() => Boolean(getMockDraft(WORKFLOW_DRAFT_KEY)));
  const [message, setMessage] = useState("");
  const latestVersion = workflow.publishedVersions.at(-1);
  const selectedStep = workflow.draft.steps[selected] ?? workflow.draft.steps[0];
  const changeDraft = (draft: WorkflowDefinition) => {
    setWorkflow({ ...workflow, draft });
    setSaved(false);
    setChecked(false);
  };
  const save = (next = workflow) => {
    saveMockDraft(WORKFLOW_DRAFT_KEY, next);
    setWorkflow(next);
    setSaved(true);
  };
  const updateSelectedStep = (patch: Partial<Omit<WorkflowStep, "id" | "name">>) => {
    changeDraft({
      steps: workflow.draft.steps.map((step, index) =>
        index === selected ? { ...step, ...patch } : step,
      ),
    });
  };
  const addStep = () => {
    const name = `新步骤 ${String(workflow.draft.steps.length + 1)}`;
    const nextStep = createStep(name, workflow.draft.steps.length);
    changeDraft({ steps: [...workflow.draft.steps, nextStep] });
    setSelected(workflow.draft.steps.length);
    setMessage(`已添加${name}，请保存草稿`);
  };
  return (
    <div className="p-5 md:p-6">
      <FocusPageHeader
        action={
          <Button
            onClick={() => {
              save();
              setMessage("草稿已保存");
            }}
          >
            <Save aria-hidden="true" />
            {saved ? "已保存" : "保存草稿"}
          </Button>
        }
        description="第一阶段使用清晰步骤编排。发布前检查依赖、循环、缺失能力包和测试项目。"
        title="工作流"
      />
      {latestVersion ? (
        <p className="mt-3 text-sm font-semibold text-[var(--sh-success)]">
          当前已发布版本 v{latestVersion.version}
        </p>
      ) : null}
      <div className="mt-7 grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3">
          <div className="mb-3 flex items-center justify-between px-2">
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">课件项目流程</h2>
            <button
              aria-label="增加步骤"
              className="grid size-9 place-items-center rounded-md hover:bg-[var(--sh-surface-soft)]"
              onClick={addStep}
              type="button"
            >
              <Plus aria-hidden="true" className="size-4" />
            </button>
          </div>
          {workflow.draft.steps.map((step, index) => (
            <button
              aria-pressed={selected === index}
              className={`mb-1 flex min-h-11 w-full items-center gap-2 rounded-[var(--sh-radius-sm)] px-3 text-left text-sm ${selected === index ? "bg-[var(--sh-brand-50)] font-semibold text-[var(--sh-brand-700)]" : "text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)]"}`}
              key={step.id}
              onClick={() => setSelected(index)}
              type="button"
            >
              <GripVertical aria-hidden="true" className="size-4 text-[var(--sh-ink-faint)]" />
              <span className="grid size-6 place-items-center rounded-full bg-[var(--sh-surface-elevated)] text-xs">
                {index + 1}
              </span>
              {step.name}
            </button>
          ))}
        </aside>
        <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 md:p-7">
          <p className="text-sm font-semibold text-[var(--sh-brand-600)]">步骤 {selected + 1}</p>
          <h2 className="mt-1 text-xl font-bold text-[var(--sh-ink-strong)]">
            {selectedStep?.name}
          </h2>
          <div className="mt-6 grid gap-5 md:grid-cols-2">
            <label>
              <span className="text-sm font-semibold">能力包</span>
              <Select
                ariaLabel="能力包"
                className="mt-2 w-full"
                onValueChange={(capability) => updateSelectedStep({ capability })}
                options={["小学数学教案生成", "课程锚点生成", "PPT 页面设计"].map((capability) => ({
                  label: capability,
                  value: capability,
                }))}
                value={selectedStep?.capability}
              />
            </label>
            <label>
              <span className="text-sm font-semibold">人工确认</span>
              <Select
                ariaLabel="人工确认"
                className="mt-2 w-full"
                onValueChange={(confirmation) => updateSelectedStep({ confirmation })}
                options={["强制确认", "按策略确认", "无需确认"].map((confirmation) => ({
                  label: confirmation,
                  value: confirmation,
                }))}
                value={selectedStep?.confirmation}
              />
            </label>
            <label>
              <span className="text-sm font-semibold">预算上限</span>
              <input
                className="mt-2 min-h-11 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] px-3"
                onChange={(event) => updateSelectedStep({ budget: event.target.value })}
                value={selectedStep?.budget}
              />
            </label>
            <label>
              <span className="text-sm font-semibold">失败重试</span>
              <Select
                ariaLabel="失败重试"
                className="mt-2 w-full"
                onValueChange={(retry) => updateSelectedStep({ retry })}
                options={["最多 2 次", "不自动重试", "最多 3 次"].map((retry) => ({
                  label: retry,
                  value: retry,
                }))}
                value={selectedStep?.retry}
              />
            </label>
          </div>
          <fieldset className="mt-6">
            <legend className="text-sm font-semibold">允许读取的上下文</legend>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {contextOptions.map((item) => (
                <label
                  className="flex items-center gap-2 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-3 text-sm"
                  key={item}
                >
                  <input
                    checked={selectedStep?.contexts.includes(item) ?? false}
                    onChange={(event) =>
                      updateSelectedStep({
                        contexts: event.target.checked
                          ? [...(selectedStep?.contexts ?? []), item]
                          : (selectedStep?.contexts ?? []).filter((context) => context !== item),
                      })
                    }
                    type="checkbox"
                  />
                  {item}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="mt-7 border-t border-[var(--sh-line-subtle)] pt-5">
            <div className="flex flex-wrap items-center gap-3">
              {checked ? (
                <span className="flex items-center gap-2 text-sm font-semibold text-[var(--sh-success)]">
                  <CheckCircle2 aria-hidden="true" className="size-4" />
                  依赖、循环、能力包和测试项目检查通过
                </span>
              ) : (
                <span className="flex items-center gap-2 text-sm text-[var(--sh-ink-muted)]">
                  <AlertTriangle aria-hidden="true" className="size-4 text-[var(--sh-warning)]" />
                  发布前必须完成工作流检查
                </span>
              )}
              <Button
                className="ml-auto"
                onClick={() => {
                  setChecked(true);
                  setMessage("发布检查已通过");
                }}
                variant="secondary"
              >
                运行发布检查
              </Button>
              <Button
                disabled={!checked}
                onClick={() => {
                  const version = (latestVersion?.version ?? 0) + 1;
                  const snapshot: PublishedWorkflowVersion = {
                    version,
                    publishedAt: new Date().toISOString(),
                    steps: workflow.draft.steps.map((step) => ({
                      ...step,
                      contexts: [...step.contexts],
                    })),
                  };
                  const next = {
                    ...workflow,
                    publishedVersions: [...workflow.publishedVersions, snapshot],
                  };
                  save(next);
                  setChecked(false);
                  setMessage(`工作流 v${String(version)} 已发布`);
                }}
              >
                发布新版本
              </Button>
            </div>
            {message ? (
              <p
                aria-live="polite"
                className="mt-3 text-sm font-semibold text-[var(--sh-brand-700)]"
              >
                {message}
              </p>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}
