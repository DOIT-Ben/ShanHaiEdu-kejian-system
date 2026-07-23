import type { GenerationJobDto } from "@/features/jobs/api/jobsApi";

export const terminalGenerationJobStatuses = new Set<GenerationJobDto["status"]>([
  "succeeded",
  "failed",
  "cancelled",
]);

export const cancellationAcknowledgedJobStatuses = new Set<GenerationJobDto["status"]>([
  ...terminalGenerationJobStatuses,
  "cancel_requested",
]);
