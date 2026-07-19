import type { ContractWorkflowStatus } from "@/entities/workflow/model";

export type AutomationMode = "manual" | "assisted" | "automatic";

export type ProjectSummary = {
  archived?: boolean;
  id: string;
  title: string;
  knowledgePoint: string;
  grade: string;
  textbookEdition: string;
  currentLesson: string;
  nextAction: string;
  progressLabel: string;
  status?: "draft" | "active" | "archived";
  updatedAt: string;
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
