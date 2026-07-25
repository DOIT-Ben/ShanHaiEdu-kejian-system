import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useRef } from "react";
import {
  getArtifact,
  getMaterialScopeArtifact,
  reviewArtifactVersion,
} from "@/features/artifacts/api/artifactsApi";
import {
  createMaterialScopeVersion,
  type CreateMaterialScopeVersionRequest,
} from "@/features/materials/api/materialsApi";

export function materialScopeArtifactKey(projectId?: string) {
  return ["projects", projectId, "material-scope", "artifact"] as const;
}

export function useMaterialScopeRuntime(projectId?: string) {
  const aggregateKey = useMemo(() => materialScopeArtifactKey(projectId), [projectId]);
  const aggregateQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => getMaterialScopeArtifact(projectId ?? ""),
    queryKey: aggregateKey,
  });
  const summary = aggregateQuery.data?.artifact;
  const detailQuery = useQuery({
    enabled: Boolean(summary?.id),
    queryFn: () => getArtifact(summary?.id ?? ""),
    queryKey: ["artifacts", summary?.id],
  });
  const candidate = detailQuery.data?.artifact;
  const artifact =
    candidate &&
    candidate.id === summary?.id &&
    candidate.project_id === projectId &&
    candidate.lesson_unit_id === null &&
    candidate.artifact_type === "material_scope"
      ? candidate
      : undefined;
  const refetch = async () => {
    await aggregateQuery.refetch();
    if (summary?.id) await detailQuery.refetch();
  };
  return {
    aggregateQuery,
    artifact,
    etag: detailQuery.data?.etag,
    latestApproval: aggregateQuery.data?.latest_approval,
    refetch,
  };
}

export function useCreateMaterialScopeMutation({
  projectId,
  refetch,
}: {
  projectId?: string;
  refetch: () => Promise<unknown>;
}) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: (input: CreateMaterialScopeVersionRequest) => {
      if (!projectId) throw new Error("PROJECT_ID_MISSING");
      intentRef.current ??= crypto.randomUUID();
      return createMaterialScopeVersion({
        idempotencyKey: intentRef.current,
        input,
        projectId,
      });
    },
    onSuccess: async () => {
      intentRef.current = undefined;
      await refetch();
    },
  });
}

export function useApproveMaterialScopeMutation({
  projectId,
  refetch,
  versionId,
}: {
  projectId?: string;
  refetch: () => Promise<unknown>;
  versionId?: string;
}) {
  const intentRef = useRef<string | undefined>(undefined);
  return useMutation({
    mutationFn: () => {
      if (!projectId || !versionId) throw new Error("MATERIAL_SCOPE_VERSION_MISSING");
      intentRef.current ??= crypto.randomUUID();
      return reviewArtifactVersion({
        artifactVersionId: versionId,
        idempotencyKey: intentRef.current,
        input: { action: "approve", comment: "教材范围已确认" },
      });
    },
    onSuccess: async () => {
      intentRef.current = undefined;
      await refetch();
    },
  });
}
