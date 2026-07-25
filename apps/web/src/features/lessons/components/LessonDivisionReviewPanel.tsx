import { CheckCircle2, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import type { AcceptedNodeRunDto, ArtifactDto } from "@/features/artifacts/api/artifactsApi";
import { ArtifactQualityStatus } from "@/features/artifacts/components/ArtifactQualityStatus";
import type { NodeRunDto } from "@/features/workflow/api/workflowApi";
import { Button, buttonVariants } from "@/shared/ui/Button";

type LessonDivisionReviewPanelProps = {
  artifact: ArtifactDto;
  busyAction?: "approve" | "quality";
  errorMessage?: string;
  onApprove: () => void;
  onQuality: () => void;
  projectId: string;
  qualityAccepted?: AcceptedNodeRunDto;
  qualityNodeRuns?: readonly NodeRunDto[];
  writeReady: boolean;
};

function recordValue(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function textValue(value: unknown) {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function lessonUnits(artifact: ArtifactDto) {
  const version = artifact.current_submitted_version ?? artifact.current_approved_version;
  const content: Record<string, unknown> | undefined = version?.content;
  const units = content?.lesson_units;
  return Array.isArray(units) ? units.map(recordValue).filter((unit) => unit !== undefined) : [];
}

export function LessonDivisionReviewPanel({
  artifact,
  busyAction,
  errorMessage,
  onApprove,
  onQuality,
  projectId,
  qualityAccepted,
  qualityNodeRuns,
  writeReady,
}: LessonDivisionReviewPanelProps) {
  const units = lessonUnits(artifact);
  const version = artifact.current_submitted_version ?? artifact.current_approved_version;
  const approved = artifact.status === "approved" && artifact.current_approved_version !== null;
  const readable = Boolean(
    version && units.length > 0 && units.every((unit) => textValue(unit.title)),
  );

  return (
    <section
      className="border-t border-[var(--sh-line-subtle)] pt-5"
      aria-labelledby="division-review-title"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold text-[var(--sh-ink-strong)]" id="division-review-title">
            审阅课时划分
          </h2>
          <p className="mt-1 text-sm leading-6 text-[var(--sh-ink-muted)]">
            以下内容来自当前 exact ArtifactVersion。质量校验通过并批准后才会建立正式课时。
          </p>
        </div>
        {version ? (
          <span className="text-sm text-[var(--sh-ink-faint)]">版本 {version.version_no}</span>
        ) : null}
      </div>

      {readable ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {units.map((unit, index) => {
            const title = textValue(unit.title) ?? "未命名课时";
            const position = typeof unit.position === "number" ? unit.position : index + 1;
            const duration =
              typeof unit.duration_minutes === "number" ? unit.duration_minutes : null;
            return (
              <article
                className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4"
                key={textValue(unit.lesson_unit_key) ?? `${String(position)}-${title}`}
              >
                <h3 className="font-semibold text-[var(--sh-ink-strong)]">
                  第 {position} 课时 · {title}
                </h3>
                {duration ? (
                  <p className="mt-2 text-xs text-[var(--sh-ink-faint)]">{duration} 分钟</p>
                ) : null}
                {textValue(unit.core_learning_outcome) ? (
                  <p className="mt-3 text-sm leading-6 text-[var(--sh-ink-default)]">
                    {textValue(unit.core_learning_outcome)}
                  </p>
                ) : null}
                {textValue(unit.material_scope) ? (
                  <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
                    {textValue(unit.material_scope)}
                  </p>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : (
        <p className="mt-4 text-sm text-[var(--sh-danger)]" role="alert">
          当前课时划分正文无法安全展示，质量校验和批准已停用。
        </p>
      )}

      {approved ? (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-success-soft)] p-4">
          <p className="flex items-center gap-2 text-sm text-[var(--sh-success)]">
            <CheckCircle2 aria-hidden="true" className="size-4" />
            课时划分已批准，正式 LessonUnit 已建立。
          </p>
          <Link
            className={buttonVariants({ variant: "secondary" })}
            to={`/app/projects/${projectId}/lessons`}
          >
            查看已建立课时
          </Link>
        </div>
      ) : (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button
            disabled={!writeReady || !readable || busyAction !== undefined}
            onClick={onQuality}
            variant="secondary"
          >
            <ShieldCheck aria-hidden="true" />
            运行课时划分质量校验
          </Button>
          <Button
            disabled={!writeReady || !readable || busyAction !== undefined}
            onClick={onApprove}
          >
            批准课时划分
          </Button>
          <ArtifactQualityStatus
            accepted={qualityAccepted}
            nodeRuns={qualityNodeRuns}
            subject="课时划分"
          />
        </div>
      )}

      {errorMessage ? (
        <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
          {errorMessage}
        </p>
      ) : null}
    </section>
  );
}
