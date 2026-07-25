import { type QueryKey, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { listProjectArtifactsPage, type ArtifactDto } from "@/features/artifacts/api/artifactsApi";
import {
  getGenerationJob,
  listProjectGenerationJobsPage,
  type GenerationJobDto,
} from "@/features/jobs/api/jobsApi";
import {
  createMaterialScopeVersion,
  getSourceMaterialFileAsset,
  listMaterialParseVersions,
  listProjectMaterialsPage,
  type MaterialParseVersionDto,
} from "@/features/materials/api/materialsApi";
import {
  getProjectWorkflow,
  prepareLessonDivision,
  startNodeRun,
} from "@/features/workflow/api/workflowApi";
import { useJobEvents } from "@/shared/api/useJobEvents";

const terminalJobStatuses = new Set<GenerationJobDto["status"]>([
  "succeeded",
  "failed",
  "cancelled",
]);

type ArtifactPage = { items: ArtifactDto[]; nextCursor: string | null };

function replaceArtifact(page: ArtifactPage | undefined, artifact: ArtifactDto): ArtifactPage {
  const items = page?.items ?? [];
  const index = items.findIndex((item) => item.id === artifact.id);
  return {
    items:
      index < 0
        ? [artifact, ...items]
        : items.map((item) => (item.id === artifact.id ? artifact : item)),
    nextCursor: page?.nextCursor ?? null,
  };
}

async function loadMaterialDetails(projectId: string, materialId: string) {
  const resource = { materialId, projectId };
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
}

function latestSucceededParse(parseVersions: MaterialParseVersionDto[]) {
  return [...parseVersions]
    .filter((version) => version.status === "succeeded" && version.page_count !== null)
    .sort((left, right) => right.version_no - left.version_no)[0];
}

export function useProjectMaterialsRuntime(projectId?: string, routeMaterialId?: string) {
  const materialsQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => listProjectMaterialsPage({ limit: 100, projectId: projectId ?? "" }),
    queryKey: ["projects", projectId, "materials"],
  });
  const selectedMaterialId =
    routeMaterialId ??
    materialsQuery.data?.items.find((material) => material.upload_status === "confirmed")?.id;
  const materialQuery = useQuery({
    enabled: Boolean(projectId && selectedMaterialId),
    queryFn: () => loadMaterialDetails(projectId ?? "", selectedMaterialId ?? ""),
    queryKey: ["projects", projectId, "materials", selectedMaterialId],
  });
  return {
    latestSucceededParse: latestSucceededParse(materialQuery.data?.parseVersions ?? []),
    materialQuery,
    materialsQuery,
    selectedMaterialId,
  };
}

export function useProjectArtifactsRuntime(projectId?: string) {
  const artifactsKey = ["projects", projectId, "artifacts"] as const;
  const artifactsQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => listProjectArtifactsPage({ limit: 100, projectId: projectId ?? "" }),
    queryKey: artifactsKey,
  });
  const materialScope = artifactsQuery.data?.items.find(
    (artifact) => artifact.artifact_type === "material_scope" && artifact.project_id === projectId,
  );
  const lessonDivision = artifactsQuery.data?.items.find(
    (artifact) => artifact.artifact_type === "lesson_division" && artifact.project_id === projectId,
  );
  return { artifactsKey, artifactsQuery, lessonDivision, materialScope };
}

export function useLessonDivisionJobRuntime(projectId?: string) {
  const [startedJobId, setStartedJobId] = useState<string>();
  const workflowQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => getProjectWorkflow(projectId ?? ""),
    queryKey: ["projects", projectId, "workflow"],
  });
  const jobsKey = ["tasks", projectId] as const;
  const jobsQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => listProjectGenerationJobsPage({ limit: 100, projectId: projectId ?? "" }),
    queryKey: jobsKey,
  });
  const recoveredJob = jobsQuery.data?.items.find(
    (job) =>
      job.project_id === projectId &&
      job.job_type === "workflow.node" &&
      job.lesson_unit_id == null &&
      Boolean(job.node_run_id),
  );
  const activeJobId = startedJobId ?? recoveredJob?.id;
  const jobQuery = useQuery({
    enabled: Boolean(activeJobId),
    placeholderData: recoveredJob,
    queryFn: () => getGenerationJob(activeJobId ?? ""),
    queryKey: ["generation-jobs", activeJobId],
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && terminalJobStatuses.has(status) ? false : 5_000;
    },
  });
  const job = jobQuery.data;
  const liveJob = Boolean(
    job && job.project_id === projectId && !terminalJobStatuses.has(job.status),
  );
  useJobEvents(liveJob ? activeJobId : undefined, liveJob ? projectId : undefined);
  return { job, jobQuery, jobsKey, jobsQuery, setStartedJobId, workflowQuery };
}

type ScopeMutationOptions = {
  artifactsKey: QueryKey;
  parseVersion?: MaterialParseVersionDto;
  projectId?: string;
  selectedMaterialId?: string;
};

export function useCreateMaterialScopeMutation({
  artifactsKey,
  parseVersion,
  projectId,
  selectedMaterialId,
}: ScopeMutationOptions) {
  const queryClient = useQueryClient();
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: ({ pageEnd, pageStart }: { pageEnd: number; pageStart: number }) => {
      if (!projectId || !selectedMaterialId || !parseVersion) {
        throw new Error("MATERIAL_SCOPE_SOURCE_MISSING");
      }
      intentRef.current ??= crypto.randomUUID();
      return createMaterialScopeVersion({
        idempotencyKey: intentRef.current,
        input: {
          material_parse_version_id: parseVersion.id,
          page_end: pageEnd,
          page_start: pageStart,
          source_material_id: selectedMaterialId,
        },
        projectId,
      });
    },
    onSuccess: (artifact) => {
      intentRef.current = undefined;
      queryClient.setQueryData<ArtifactPage>(artifactsKey, (current) =>
        replaceArtifact(current, artifact),
      );
    },
  });
}

type GenerationMutationOptions = {
  jobsKey: QueryKey;
  materialScope?: ArtifactDto;
  onStarted: (jobId: string) => void;
  projectId?: string;
};

export function useLessonDivisionGenerationMutation({
  jobsKey,
  materialScope,
  onStarted,
  projectId,
}: GenerationMutationOptions) {
  const queryClient = useQueryClient();
  const prepareIntentRef = useRef<string | undefined>(undefined);
  const startIntentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: async () => {
      const versionId =
        materialScope?.status === "approved"
          ? materialScope.current_approved_version?.id
          : undefined;
      if (!projectId || !versionId) throw new Error("APPROVED_MATERIAL_SCOPE_MISSING");
      prepareIntentRef.current ??= crypto.randomUUID();
      startIntentRef.current ??= crypto.randomUUID();
      const node = await prepareLessonDivision({
        idempotencyKey: prepareIntentRef.current,
        materialScopeArtifactVersionId: versionId,
        projectId,
      });
      return startNodeRun({ idempotencyKey: startIntentRef.current, nodeRunId: node.id });
    },
    onSuccess: (accepted) => {
      prepareIntentRef.current = undefined;
      startIntentRef.current = undefined;
      onStarted(accepted.job_id);
      void queryClient.invalidateQueries({ exact: true, queryKey: jobsKey });
    },
  });
}
