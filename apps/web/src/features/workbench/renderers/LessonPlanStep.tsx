import {
  ArrowRight,
  Check,
  History,
  MessageSquareText,
  PencilLine,
  SearchCheck,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { createLessonPlanData, lessonPlanData } from "@/features/content-definition/fixtures";
import type { ContentData } from "@/features/content-definition/model";
import {
  MarkdownDocument,
  type DocumentMode,
} from "@/features/workbench/components/MarkdownDocument";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import { parseLessonPlan, serializeLessonPlan } from "@/features/workbench/lib/documentMarkdown";
import { markLessonPlanDependentsStale } from "@/features/workbench/lib/invalidateDependents";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import { saveMockDraft, updateMockNodeState, useMockRuntime } from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { IconButton } from "@/shared/ui/IconButton";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { demoProjectId } from "@/shared/data/mockData";

export function LessonPlanStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const lesson = getApprovedProjectLessons(runtime, projectId).find((item) => item.id === lessonId);
  const project = runtime.projects.find((item) => item.id === projectId);
  const planDraftKey = `project:${projectId}:lesson:${lessonId}:lesson-plan`;
  const approvedPlanKey = `${planDraftKey}:approved`;
  const editingKey = `${planDraftKey}:editing`;
  const savedPlan = runtime.drafts[planDraftKey]?.value;
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:lesson-plan`];
  const stale = nodeState?.status === "stale";
  const nodeApproved = nodeState?.status === "approved";
  const editing = runtime.drafts[editingKey]?.value === true;
  const approved = nodeApproved && !editing;
  const approvedSnapshot = runtime.drafts[approvedPlanKey]?.value as
    { markdown?: unknown } | undefined;
  const documentTitle =
    lesson?.title.replace(/^第\s*\d+\s*课时\s*·\s*/, "") ?? project?.knowledge_point ?? "教案";
  const fallbackPlanData: ContentData =
    projectId === demoProjectId
      ? lessonPlanData
      : createLessonPlanData(project?.knowledge_point ?? documentTitle, lesson?.scope);
  const approvedPlan = runtime.drafts[approvedPlanKey]?.value;
  const initialData = approved
    ? approvedPlan && typeof approvedPlan === "object"
      ? (approvedPlan as ContentData)
      : fallbackPlanData
    : savedPlan && typeof savedPlan === "object"
      ? (savedPlan as ContentData)
      : approvedPlan && typeof approvedPlan === "object"
        ? (approvedPlan as ContentData)
        : fallbackPlanData;
  const documentSubtitle = `${project?.grade ?? "年级待确认"}数学 · ${lesson?.title ?? "当前课时"}`;
  const savedMarkdown =
    typeof initialData.markdown === "string"
      ? initialData.markdown
      : serializeLessonPlan(initialData, documentTitle, documentSubtitle);
  const [draftData, setDraftData] = useState<ContentData>(initialData);
  const [markdown, setMarkdown] = useState(savedMarkdown);
  const [mode, setMode] = useState<DocumentMode>("preview");
  const [dirty, setDirty] = useState(false);
  const { openContextDrawer } = useWorkbenchUi();

  const savePlan = () => {
    if (approved) return;
    const nextData = parseLessonPlan(markdown, draftData);
    setDraftData(nextData);
    saveMockDraft(
      planDraftKey,
      { ...nextData, markdown },
      {
        lessonId,
        nodeKey: "lesson-plan",
        projectId,
      },
    );
    setDirty(false);
  };

  const approvePlan = () => {
    const nextData = parseLessonPlan(markdown, draftData);
    const changed =
      nodeApproved &&
      (typeof approvedSnapshot?.markdown !== "string" || approvedSnapshot.markdown !== markdown);
    if (changed) markLessonPlanDependentsStale(runtime, projectId, lessonId);
    setDraftData(nextData);
    saveMockDraft(
      planDraftKey,
      { ...nextData, markdown },
      {
        lessonId,
        nodeKey: "lesson-plan",
        projectId,
      },
    );
    saveMockDraft(
      approvedPlanKey,
      { ...nextData, markdown },
      { lessonId, nodeKey: "lesson-plan", projectId },
    );
    saveMockDraft(editingKey, false, { lessonId, nodeKey: "lesson-plan", projectId });
    if (!nodeApproved || changed) {
      updateMockNodeState(projectId, lessonId, "lesson-plan", {
        stale_reason: null,
        title: "生成教案",
        status: "approved",
      });
    }
    setDirty(false);
  };

  return (
    <WorkbenchPageFrame width="document">
      <FocusPageHeader
        action={
          approved ? (
            <>
              <Button
                onClick={() => {
                  if (!runtime.drafts[approvedPlanKey]) {
                    saveMockDraft(
                      approvedPlanKey,
                      { ...draftData, markdown },
                      { lessonId, nodeKey: "lesson-plan", projectId },
                    );
                  }
                  saveMockDraft(editingKey, true, {
                    lessonId,
                    nodeKey: "lesson-plan",
                    projectId,
                  });
                }}
                size="md"
                variant="secondary"
              >
                <PencilLine aria-hidden="true" />
                重新编辑教案
              </Button>
              <Button asChild size="md">
                <Link to={`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-outline`}>
                  安排 PPT 页面
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </>
          ) : (
            <Button onClick={approvePlan} size="md">
              <Check aria-hidden="true" />
              {editing ? "确认新教案" : "确认教案"}
            </Button>
          )
        }
        eyebrow={`当前要做：修改并确认${lesson?.title ?? "当前课时"}教案`}
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : "review_required"} />
        }
        title={documentTitle}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <MarkdownDocument
        ariaLabel="教案正文"
        dirty={dirty}
        extraActions={
          <>
            <IconButton label="查看参考内容" onClick={() => openContextDrawer("references")}>
              <MessageSquareText aria-hidden="true" />
            </IconButton>
            <IconButton label="查看检查结果" onClick={() => openContextDrawer("checks")}>
              <SearchCheck aria-hidden="true" />
            </IconButton>
            <IconButton label="查看历史记录" onClick={() => openContextDrawer("history")}>
              <History aria-hidden="true" />
            </IconButton>
          </>
        }
        markdown={markdown}
        mode={mode}
        onChange={(nextMarkdown) => {
          if (approved) return;
          setMarkdown(nextMarkdown);
          setDraftData(parseLessonPlan(nextMarkdown, draftData));
          setDirty(true);
        }}
        onModeChange={setMode}
        onSave={savePlan}
        readOnly={approved}
        title="完整教案"
      />
    </WorkbenchPageFrame>
  );
}
