import { ArrowRight, Check } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  MarkdownDocument,
  type DocumentMode,
} from "@/features/workbench/components/MarkdownDocument";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import { getApprovedDraftValue } from "@/features/workbench/lib/approvedDraft";
import { markPptDesignDependentsStale } from "@/features/workbench/lib/invalidateDependents";
import { readPptOutlinePages, type PptOutlinePage } from "@/features/workbench/lib/pptOutline";
import { saveMockDraft, updateMockNodeState, useMockRuntime } from "@/shared/api/mocks/runtime";
import { Button, buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";

function visualDirection(page: PptOutlinePage) {
  if (page.pageType === "cover") {
    return "主题统领型课堂主视觉，16:9 全幅画面；标题和课程信息保持为可编辑文字。";
  }
  if (page.pageType === "summary") {
    return "纯白背景，以一张关系总结主视觉承载本页核心回顾，避免信息堆叠。";
  }
  return "纯白背景，以课堂情境、实物教具或数学关系图作为唯一主视觉。";
}

function buildDesignMarkdown(pages: PptOutlinePage[], topic: string) {
  const sections = pages.map(
    (page, index) => `## 第 ${String(index + 1)} 页 · ${page.title}

- **教学任务**：${page.task}
- **内容来源**：${page.source}
- **学生视线中心**：先看清本页唯一需要理解的关系，再阅读问题或结论。
- **主视觉设计**：${visualDirection(page)}
- **可编辑内容**：标题、问题、数字、算式、答案、标注和数学图形全部使用 PPT 原生元素。
- **版式安排**：主视觉占主要空间，文字区控制在一至两个阅读层级，保留投影安全边距。
- **图片资产需求**：生成一张无水印、无 Logo、无准确文字数字的 16:9 课堂画面素材。
- **课堂互动**：教师围绕“${page.task}”组织一次观察、比较或表达。
`,
  );
  return `# ${topic} · PPT 逐页设计稿

> 本设计稿是页面装配、图片资产和最终 PPTX 的共同依据。正文页使用纯白背景，准确文字与数学信息保持可编辑。

${sections.join("\n")}`;
}

export function PptDesignStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const topic = project?.knowledge_point ?? "本课知识点";
  const outline =
    readPptOutlinePages(getApprovedDraftValue(runtime, projectId, lessonId, "ppt-outline")) ?? [];
  const draftKey = `project:${projectId}:lesson:${lessonId}:ppt-design`;
  const approvedKey = `${draftKey}:approved`;
  const saved = runtime.drafts[draftKey]?.value;
  const approvedSaved = getApprovedDraftValue<string>(runtime, projectId, lessonId, "ppt-design");
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:ppt-design`];
  const [markdown, setMarkdown] = useState(() =>
    typeof saved === "string" ? saved : (approvedSaved ?? buildDesignMarkdown(outline, topic)),
  );
  const [mode, setMode] = useState<DocumentMode>("preview");
  const [dirty, setDirty] = useState(false);
  const approved = nodeState?.status === "approved" && !dirty;
  const stale = nodeState?.status === "stale";

  const saveDraft = () => {
    saveMockDraft(draftKey, markdown, { lessonId, nodeKey: "ppt-design", projectId });
    setDirty(false);
    if (nodeState?.status === "approved" && approvedSaved !== markdown) {
      updateMockNodeState(projectId, lessonId, "ppt-design", {
        status: "review_required",
        title: "确认逐页设计稿",
      });
    }
  };

  const approve = () => {
    if (approvedSaved && approvedSaved !== markdown) {
      markPptDesignDependentsStale(runtime, projectId, lessonId);
    }
    saveMockDraft(draftKey, markdown, { lessonId, nodeKey: "ppt-design", projectId });
    saveMockDraft(approvedKey, markdown, { lessonId, nodeKey: "ppt-design", projectId });
    updateMockNodeState(projectId, lessonId, "ppt-design", {
      stale_reason: null,
      status: "approved",
      title: "确认逐页设计稿",
    });
    setDirty(false);
    setMode("preview");
  };

  return (
    <WorkbenchPageFrame width="workspace">
      <FocusPageHeader
        action={
          approved ? (
            <Link
              className={buttonVariants({ size: "md" })}
              to={`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-cover`}
            >
              设计课件封面
              <ArrowRight aria-hidden="true" />
            </Link>
          ) : (
            <Button disabled={!markdown.trim()} onClick={approve} size="md">
              <Check aria-hidden="true" />
              确认设计稿
            </Button>
          )
        }
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : "review_required"} />
        }
        title={`${String(outline.length)} 页 PPT 逐页设计稿`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <MarkdownDocument
        ariaLabel="PPT 逐页设计稿正文"
        dirty={dirty}
        markdown={markdown}
        mode={mode}
        onChange={(value) => {
          setMarkdown(value);
          setDirty(true);
        }}
        onModeChange={setMode}
        onSave={saveDraft}
        title="完整设计稿"
      />
    </WorkbenchPageFrame>
  );
}
