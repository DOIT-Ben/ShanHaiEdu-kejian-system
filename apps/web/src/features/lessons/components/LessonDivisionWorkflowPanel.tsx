import { Layers3 } from "lucide-react";
import { LessonDivisionArtifactPanel } from "@/features/lessons/components/LessonDivisionArtifactPanel";
import { LessonDivisionGenerationPanel } from "@/features/lessons/components/LessonDivisionGenerationPanel";
import { useLessonDivisionArtifactRuntime } from "@/features/lessons/hooks/useLessonDivisionWorkflow";
import { StatusBadge } from "@/shared/ui/StatusBadge";

export function LessonDivisionWorkflowPanel({
  materialScopeVersionId,
  projectId,
}: {
  materialScopeVersionId?: string;
  projectId: string;
}) {
  const artifactRuntime = useLessonDivisionArtifactRuntime(projectId);
  const approved =
    artifactRuntime.artifact?.status === "approved" &&
    artifactRuntime.artifact.current_approved_version?.id ===
      artifactRuntime.latestApproval?.artifact_version_id &&
    artifactRuntime.latestApproval?.action === "approve";

  return (
    <section
      className="border-t border-[var(--sh-line-subtle)] pt-6"
      aria-labelledby="division-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Layers3 aria-hidden="true" className="size-5 text-[var(--sh-brand-600)]" />
            <h2 className="text-lg font-semibold text-[var(--sh-ink-strong)]" id="division-title">
              课时划分
            </h2>
          </div>
          <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
            将已确认教材范围划分为可独立实施的课时。
          </p>
        </div>
        {artifactRuntime.artifact ? (
          <StatusBadge status={approved ? "approved" : "review_required"} />
        ) : null}
      </div>

      <LessonDivisionGenerationPanel
        artifactExists={artifactRuntime.artifact !== undefined}
        materialScopeVersionId={materialScopeVersionId}
        projectId={projectId}
      />
      <LessonDivisionArtifactPanel
        approved={approved}
        projectId={projectId}
        runtime={artifactRuntime}
      />
    </section>
  );
}
