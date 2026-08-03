import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, BookOpen } from "lucide-react";
import { useRef } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  getSourceMaterialFileAsset,
  listMaterialParsePages,
  listMaterialParseVersions,
  listProjectTextbookMaterials,
  retryMaterialParse,
} from "@/features/materials/api/materialsApi";
import { MaterialDetailsPanel } from "@/features/materials/components/MaterialDetailsPanel";
import { MaterialScopePanel } from "@/features/materials/components/MaterialScopePanel";
import { ProjectMaterialUploadPanel } from "@/features/materials/components/ProjectMaterialUploadPanel";
import { useMaterialScopeRuntime } from "@/features/materials/hooks/useMaterialScopeWorkflow";
import { materialScopeVersionMatches } from "@/features/materials/lib/materialScopeIdentity";
import { LessonDivisionWorkflowPanel } from "@/features/lessons/components/LessonDivisionWorkflowPanel";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { useProjectEvents } from "@/shared/api/useProjectEvents";
import { buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

export function RuntimeMaterialsPage() {
  const { materialId, projectId } = useParams();
  const navigate = useNavigate();
  useProjectEvents(projectId);
  const materialsQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => listProjectTextbookMaterials(projectId ?? ""),
    queryKey: ["projects", projectId, "materials"],
  });
  const scopeRuntime = useMaterialScopeRuntime(projectId);

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
  const retryIntentRef = useRef<string | null>(null);
  const retryMutation = useMutation({
    mutationFn: () => {
      const fileAssetVersionId = materialQuery.data?.asset?.current_version.id;
      if (!materialId || !projectId || !fileAssetVersionId) {
        throw new Error("MATERIAL_PARSE_RETRY_INPUT_MISSING");
      }
      retryIntentRef.current ??= crypto.randomUUID();
      return retryMaterialParse({
        fileAssetVersionId,
        idempotencyKey: retryIntentRef.current,
        materialId,
        projectId,
      });
    },
    onSuccess: (job) => {
      retryIntentRef.current = null;
      const params = new URLSearchParams({ jobId: job.job_id, materialId: materialId ?? "" });
      void navigate(`/app/projects/${projectId ?? ""}/setup?${params.toString()}`);
    },
  });
  const selectedParseVersion = materialQuery.data?.parseVersions.find(
    (version) => version.status === "succeeded",
  );
  const pagesQuery = useQuery({
    enabled: Boolean(projectId && materialId && selectedParseVersion?.id),
    queryFn: () =>
      listMaterialParsePages({
        materialId: materialId ?? "",
        parseVersionId: selectedParseVersion?.id ?? "",
        projectId: projectId ?? "",
      }),
    queryKey: [
      "projects",
      projectId,
      "materials",
      materialId,
      "parse-versions",
      selectedParseVersion?.id,
      "pages",
    ],
  });
  const currentApprovedScopeVersion = scopeRuntime.artifact?.current_approved_version;
  const latestScopeApproval = scopeRuntime.latestApproval;
  const approvedScopeVersionId =
    scopeRuntime.artifact?.status === "approved" &&
    currentApprovedScopeVersion &&
    latestScopeApproval &&
    currentApprovedScopeVersion.id === latestScopeApproval.artifact_version_id &&
    latestScopeApproval.action === "approve" &&
    materialScopeVersionMatches(currentApprovedScopeVersion, materialId, selectedParseVersion?.id)
      ? currentApprovedScopeVersion.id
      : undefined;

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
        description="核对教材解析页，确认教学范围并形成可执行的课时划分。"
        title="教材与课时划分"
      />

      <div className="mt-5">
        {materialId ? (
          <div className="space-y-6">
            <MaterialDetailsPanel
              asset={materialQuery.data?.asset}
              errorMessage={
                retryMutation.isError
                  ? runtimeErrorMessage(
                      retryMutation.error,
                      "教材没有开始重新解析，请检查网络后重试。",
                    )
                  : materialQuery.isError
                    ? runtimeErrorMessage(materialQuery.error, "教材状态暂时无法读取，请稍后重试。")
                    : materialQuery.data?.partialError
              }
              loading={materialQuery.isFetching}
              onRefresh={() => void materialQuery.refetch()}
              onRetry={() => retryMutation.mutate()}
              parseVersions={materialQuery.data?.parseVersions ?? []}
              retryDisabled={!isCsrfTokenAvailable()}
              retrying={retryMutation.isPending}
            />

            {selectedParseVersion ? (
              <>
                {pagesQuery.error ? (
                  <p className="text-sm text-[var(--sh-danger)]" role="alert">
                    {runtimeErrorMessage(pagesQuery.error, "教材页事实暂时无法读取。")}
                  </p>
                ) : null}
                <MaterialScopePanel
                  materialId={materialId}
                  pages={pagesQuery.data ?? []}
                  parseVersion={selectedParseVersion}
                  projectId={projectId}
                  runtime={scopeRuntime}
                />
                <LessonDivisionWorkflowPanel
                  materialScopeVersionId={approvedScopeVersionId}
                  projectId={projectId}
                />
              </>
            ) : (
              <p className="border-t border-[var(--sh-line-subtle)] pt-5 text-sm text-[var(--sh-ink-muted)]">
                教材解析成功后即可确认范围并生成课时划分。
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-6">
            <ProjectMaterialUploadPanel
              onAccepted={({ jobId, materialId: acceptedMaterialId }) => {
                const params = new URLSearchParams({ jobId, materialId: acceptedMaterialId });
                void navigate(`/app/projects/${projectId}/setup?${params.toString()}`);
              }}
              projectId={projectId}
            />
            <section aria-labelledby="material-list-title">
              <h2
                className="text-lg font-semibold text-[var(--sh-ink-strong)]"
                id="material-list-title"
              >
                选择教材
              </h2>
              {materialsQuery.isLoading ? (
                <p className="mt-3 text-sm text-[var(--sh-ink-muted)]" role="status">
                  正在读取项目教材
                </p>
              ) : materialsQuery.error ? (
                <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
                  {runtimeErrorMessage(materialsQuery.error, "项目教材暂时无法读取。")}
                </p>
              ) : materialsQuery.data?.length ? (
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {materialsQuery.data.map((material) => (
                    <Link
                      className="flex min-h-24 items-center gap-3 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4 transition-colors hover:border-[var(--sh-brand-300)] hover:bg-[var(--sh-brand-50)]"
                      key={material.id}
                      to={`/app/projects/${projectId}/materials/${material.id}`}
                    >
                      <span className="grid size-10 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]">
                        <BookOpen aria-hidden="true" />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate font-semibold text-[var(--sh-ink-strong)]">
                          {material.original_filename}
                        </span>
                        <span className="mt-1 block text-sm text-[var(--sh-ink-muted)]">
                          {material.upload_status === "confirmed" ? "已上传" : "处理中"}
                        </span>
                      </span>
                    </Link>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-sm text-[var(--sh-ink-muted)]">当前项目还没有教材。</p>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
