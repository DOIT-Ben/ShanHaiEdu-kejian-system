import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import {
  getSourceMaterialFileAsset,
  listMaterialParseVersions,
} from "@/features/materials/api/materialsApi";
import { MaterialDetailsPanel } from "@/features/materials/components/MaterialDetailsPanel";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { useProjectEvents } from "@/shared/api/useProjectEvents";
import { buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

export function RuntimeMaterialsPage() {
  const { materialId, projectId } = useParams();
  useProjectEvents(projectId);

  const materialQuery = useQuery({
    enabled: Boolean(projectId && materialId),
    queryFn: async () => {
      const resource = { materialId: materialId ?? "", projectId: projectId ?? "" };
      const [fileAssetResult, parseVersionsResult] = await Promise.allSettled([
        getSourceMaterialFileAsset(resource),
        listMaterialParseVersions(resource),
      ]);
      if (fileAssetResult.status === "rejected" && parseVersionsResult.status === "rejected") {
        throw new AggregateError(
          [fileAssetResult.reason, parseVersionsResult.reason],
          "Material details could not be loaded.",
        );
      }
      return {
        asset: fileAssetResult.status === "fulfilled" ? fileAssetResult.value.asset : undefined,
        parseVersions: parseVersionsResult.status === "fulfilled" ? parseVersionsResult.value : [],
        partialError:
          fileAssetResult.status === "rejected"
            ? "教材文件暂时无法读取，已保留成功读取的解析记录。"
            : parseVersionsResult.status === "rejected"
              ? "解析记录暂时无法读取，已保留成功读取的教材文件。"
              : undefined,
      };
    },
    queryKey: ["projects", projectId, "materials", materialId],
  });

  if (!projectId) return null;

  return (
    <div className="mx-auto max-w-[980px] px-4 py-5 md:px-6 lg:px-8">
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
        description="查看教材文件校验与解析记录。"
        title="教材与解析结果"
      />

      <div className="mt-5">
        {materialId ? (
          <MaterialDetailsPanel
            asset={materialQuery.data?.asset}
            errorMessage={
              materialQuery.isError
                ? runtimeErrorMessage(materialQuery.error, "教材状态暂时无法读取，请稍后重试。")
                : materialQuery.data?.partialError
            }
            loading={materialQuery.isFetching}
            onRefresh={() => void materialQuery.refetch()}
            parseVersions={materialQuery.data?.parseVersions ?? []}
          />
        ) : (
          <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6">
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">教材详情暂时无法打开</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
              当前项目没有可直接打开的教材记录入口。新上传的教材完成处理后，可从对应任务进入详情。
            </p>
          </section>
        )}
      </div>
    </div>
  );
}
