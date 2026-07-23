import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getArtifact } from "@/features/artifacts/api/artifactsApi";
import { ArtifactWorkbench } from "@/features/artifacts/components/ArtifactWorkbench";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { useProjectEvents } from "@/shared/api/useProjectEvents";
import { Button, buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

const artifactTitles: Record<string, string> = {
  intro_option_set: "课堂导入方案",
  lesson_plan: "课时教案",
  ppt: "课堂课件",
  video: "课堂视频",
};

export function RuntimeArtifactPage() {
  const { artifactId, projectId } = useParams();

  const artifactKey = ["artifacts", artifactId] as const;
  const artifactQuery = useQuery({
    enabled: Boolean(artifactId),
    queryFn: () => getArtifact(artifactId ?? ""),
    queryKey: artifactKey,
  });
  const artifact = artifactQuery.data?.artifact;
  const artifactOwnedByProject = Boolean(projectId && artifact?.project_id === projectId);
  useProjectEvents(artifactOwnedByProject ? projectId : undefined);

  if (!projectId || !artifactId) return null;

  return (
    <div className="mx-auto max-w-[1060px] px-4 py-5 md:px-6 lg:px-8">
      <FocusPageHeader
        action={
          <Link
            className={buttonVariants({ variant: "secondary" })}
            to={`/app/projects/${projectId}`}
          >
            <ArrowLeft aria-hidden="true" />
            返回项目
          </Link>
        }
        description="当前只显示版本状态，正文查看与审核暂不可用。"
        title="内容版本"
      />

      <div className="mt-5">
        {artifactQuery.isLoading ? (
          <div
            className="h-56 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
            role="status"
          >
            <span className="sr-only">正在读取内容版本</span>
          </div>
        ) : artifactQuery.isError || !artifact ? (
          <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6">
            <p className="text-sm text-[var(--sh-danger)]" role="alert">
              {runtimeErrorMessage(artifactQuery.error, "内容版本暂时无法读取，请稍后重试。")}
            </p>
            <Button
              className="mt-4"
              onClick={() => void artifactQuery.refetch()}
              variant="secondary"
            >
              重新读取内容
            </Button>
          </section>
        ) : !artifactOwnedByProject ? (
          <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6">
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">内容版本暂时无法打开</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
              请返回当前项目，从内容列表重新进入。
            </p>
          </section>
        ) : (
          <>
            <p
              className="mb-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm leading-6 text-[var(--sh-warning)]"
              role="status"
            >
              当前只显示版本状态，正文查看与审核暂不可用。为避免误操作，草稿保存、版本提交和批准均已停用。
            </p>
            <ArtifactWorkbench
              artifact={artifact}
              title={artifactTitles[artifact.artifact_type] ?? "项目内容"}
            />
          </>
        )}
      </div>
    </div>
  );
}
