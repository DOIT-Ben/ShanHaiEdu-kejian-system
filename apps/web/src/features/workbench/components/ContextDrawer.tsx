import * as Dialog from "@radix-ui/react-dialog";
import { BookOpen, CheckCircle2, History, LoaderCircle, Settings2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { createTopicIntroOptions, introOptions } from "@/features/intro-options/data";
import {
  readIntroOptionsDraft,
  regeneratePreviewedIntroOption,
} from "@/features/intro-options/state";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import {
  getMockRuntimeState,
  saveMockDraft,
  updateMockNodeState,
  useMockRuntime,
} from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { IconButton } from "@/shared/ui/IconButton";
import { demoProjectId } from "@/shared/data/mockData";

const tabContent = {
  references: {
    title: "参考内容",
    icon: BookOpen,
    body: "当前作品引用教材第 82—84 页和已批准课时范围。点击具体字段可查看对应页码证据。",
  },
  prompt: {
    title: "内容要求",
    icon: Settings2,
    body: "写下你希望重点调整的内容。课程范围和适龄要求会保持不变。",
  },
  checks: {
    title: "检查结果",
    icon: CheckCircle2,
    body: "知识范围、数学表达、必填结构和提前讲授检查已通过。仍有 2 条表达建议需要你判断。",
  },
  history: {
    title: "历史记录",
    icon: History,
    body: "当前为第 3 版草稿。上一版保留在版本记录中，批准新版本后仅标记实际受影响内容。",
  },
};

export function ContextDrawer() {
  const { lessonId = "", projectId = "", stepKey = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const lesson = getApprovedProjectLessons(runtime, projectId).find((item) => item.id === lessonId);
  const availableIntroOptions =
    projectId === demoProjectId || !project
      ? introOptions
      : createTopicIntroOptions(project.knowledge_point);
  const { closeContextDrawer, contextDrawerOpen, contextTab } = useWorkbenchUi();
  const current = tabContent[contextTab];
  const Icon = current.icon;
  const promptKey = `project:${projectId}:lesson:${lessonId}:${stepKey}:prompt-requirements`;
  const legacyPromptKey = `project:${projectId}:lesson:${lessonId}:prompt-requirements`;
  const savedPrompt = runtime.drafts[promptKey]?.value ?? runtime.drafts[legacyPromptKey]?.value;
  const prompt =
    typeof savedPrompt === "string"
      ? savedPrompt
      : stepKey === "intro-options"
        ? `先独立构思适合${project?.grade ?? "小学生"}观察的生活、科学或故事情境；独立创意阶段不读取课程标题和知识点。创意冻结后，再把课堂首问锚定到已批准课时范围，并且不提前讲出结论。`
        : `请围绕${project?.knowledge_point ?? lesson?.title ?? "本课知识点"}制作当前课堂内容，面向${project?.grade ?? "小学生"}，严格使用已批准课时范围“${lesson?.scope ?? "当前课时范围"}”，保留学生观察、表达和验证的空间。`;
  const [promptInput, setPromptInput] = useState(prompt);
  const [feedback, setFeedback] = useState("");
  const [regenerating, setRegenerating] = useState(false);
  const [regenerationComplete, setRegenerationComplete] = useState(false);
  const timerRef = useRef<number | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (contextDrawerOpen && contextTab === "prompt") {
      setPromptInput(prompt);
    }
  }, [contextDrawerOpen, contextTab, prompt]);

  useEffect(
    () => () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    },
    [],
  );

  const saveRequirements = () => {
    saveMockDraft(promptKey, promptInput, {
      lessonId,
      nodeKey: `${stepKey}:prompt-requirements`,
      projectId,
    });
    setRegenerationComplete(false);
    setFeedback("内容要求已保存");
  };

  const closePanel = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setFeedback("");
    setRegenerating(false);
    setRegenerationComplete(false);
    closeContextDrawer();
  };

  const regenerateIntroOption = () => {
    const defaultOption = availableIntroOptions[0];
    if (!defaultOption) return;
    saveRequirements();
    setRegenerating(true);
    setRegenerationComplete(false);
    setFeedback("正在按新要求准备方案");
    timerRef.current = window.setTimeout(() => {
      const introDraftKey = `project:${projectId}:lesson:${lessonId}:intro-options`;
      const introDraft = readIntroOptionsDraft(
        getMockRuntimeState().drafts[introDraftKey]?.value,
        defaultOption.key,
      );
      const selectedOption =
        availableIntroOptions.find((option) => option.key === introDraft.previewKey) ??
        defaultOption;
      const nextDraft = regeneratePreviewedIntroOption(introDraft, selectedOption, promptInput);
      saveMockDraft(introDraftKey, nextDraft, {
        lessonId,
        nodeKey: "intro-options",
        projectId,
      });
      updateMockNodeState(projectId, lessonId, "intro-options", {
        status: "review_required",
        title: "选择课堂导入",
      });
      setRegenerating(false);
      setRegenerationComplete(true);
      setFeedback("新方案已生成，采用后才会替换当前方案");
      timerRef.current = null;
    }, 650);
  };

  return (
    <Dialog.Root
      onOpenChange={(open) => {
        if (!open && regenerating) {
          setFeedback("正在生成，完成后即可关闭");
          return;
        }
        if (!open) closePanel();
      }}
      open={contextDrawerOpen}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[var(--sh-overlay-scrim)] backdrop-blur-[1px]" />
        <Dialog.Content
          className="fixed inset-y-0 right-0 z-50 w-[min(100%,var(--sh-advanced-drawer-width))] overflow-y-auto border-l border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6 shadow-[var(--sh-shadow-floating)]"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            returnFocusRef.current =
              document.activeElement instanceof HTMLElement ? document.activeElement : null;
            contentRef.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            returnFocusRef.current?.focus();
          }}
          ref={contentRef}
          style={{ outline: "none" }}
          tabIndex={-1}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-600)]">
                <Icon aria-hidden="true" className="size-5" />
              </span>
              <Dialog.Title className="text-lg font-semibold text-[var(--sh-ink-strong)]">
                {current.title}
              </Dialog.Title>
            </div>
            <Dialog.Close asChild>
              <IconButton
                disabled={regenerating}
                label={regenerating ? "生成完成后可关闭" : "关闭面板"}
              >
                <X aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-5 text-sm leading-7 text-[var(--sh-ink-muted)]">
            {current.body}
          </Dialog.Description>

          {contextTab === "prompt" ? (
            <div className="mt-6 space-y-5">
              <label className="block">
                <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">
                  你希望怎样调整
                </span>
                <textarea
                  className="mt-2 min-h-48 w-full resize-y rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] p-3 text-sm outline-none focus:border-[var(--sh-brand-500)]"
                  onChange={(event) => setPromptInput(event.target.value)}
                  value={promptInput}
                />
              </label>
              <div>
                <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">必须遵守</p>
                <ul className="mt-2 space-y-2 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-4 text-sm text-[var(--sh-ink-muted)]">
                  <li>不超出本课时已经确认的教学范围</li>
                  <li>使用准确、适合小学生理解的数学表达</li>
                  <li>课堂导入只留下问题，不提前讲出结论</li>
                </ul>
              </div>
              <div className="flex flex-wrap justify-end gap-2 border-t border-[var(--sh-line-subtle)] pt-4">
                <Button disabled={regenerating} onClick={saveRequirements} variant="secondary">
                  保存要求
                </Button>
                {stepKey === "intro-options" ? (
                  regenerationComplete ? (
                    <Button onClick={closePanel}>查看新方案</Button>
                  ) : (
                    <Button disabled={regenerating} onClick={regenerateIntroOption}>
                      {regenerating ? (
                        <LoaderCircle
                          aria-hidden="true"
                          className="animate-spin motion-reduce:animate-none"
                        />
                      ) : null}
                      {regenerating ? "正在重新生成" : "按新要求重新生成"}
                    </Button>
                  )
                ) : null}
              </div>
              <p
                aria-live="polite"
                className="min-h-5 text-sm text-[var(--sh-success-strong)]"
                role="status"
              >
                {feedback}
              </p>
            </div>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
