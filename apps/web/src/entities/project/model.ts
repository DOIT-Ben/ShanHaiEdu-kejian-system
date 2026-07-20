import type { ContractWorkflowStatus } from "@/entities/workflow/model";

export type AutomationMode = "manual" | "assisted" | "automatic";

export type ProjectSummary = {
  archived?: boolean;
  id: string;
  title: string;
  knowledgePoint: string;
  grade: string;
  textbookEdition: string;
  /** Optional until the lesson/workflow aggregate endpoint supplies it. */
  currentLesson?: string;
  /** Optional until the workflow aggregate endpoint supplies a real next action. */
  nextAction?: string;
  /** A status label, not a completion percentage or inferred workflow progress. */
  progressLabel?: string;
  status?: "draft" | "active" | "archived";
  updatedAt: string;
  /** Raw timestamp retained for recent-activity ordering; never shown directly. */
  updatedAtIso?: string;
};

export type LessonSummary = {
  id: string;
  title: string;
  scope: string;
  duration: number;
  planStatus: ContractWorkflowStatus;
  introStatus: ContractWorkflowStatus;
  pptStatus: ContractWorkflowStatus;
  videoStatus: ContractWorkflowStatus;
};
