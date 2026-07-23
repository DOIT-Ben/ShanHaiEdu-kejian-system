import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  bindProjectAsset,
  getProjectAssetPackage,
  listProjectAssetSlots,
  unbindProjectAsset,
  type BindAssetRequest,
  type ProjectAssetSlotDto,
} from "@/features/assets/api/assetsApi";
import { ProjectAssetSlotsPanel } from "@/features/assets/components/ProjectAssetSlotsPanel";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { useProjectEvents } from "@/shared/api/useProjectEvents";
import { Button, buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

type BindIntent = {
  input: BindAssetRequest;
  slotId: string;
};

type BindMutationIntent = BindIntent & {
  idempotencyKey: string;
  signature: string;
};

type UnbindMutationIntent = {
  bindingId: string;
  idempotencyKey: string;
};

function bindIntentSignature({ input, slotId }: BindIntent) {
  return JSON.stringify([
    slotId,
    input.file_asset_version_id,
    input.source_artifact_version_id ?? null,
    input.replace_mode,
    input.position ?? null,
  ]);
}

async function collectAssetPages<T>(
  loadPage: (cursor?: string) => Promise<{
    items: T[];
    nextCursor?: string;
  }>,
) {
  const items: T[] = [];
  const visitedCursors = new Set<string>();
  let cursor: string | undefined;

  do {
    const page = await loadPage(cursor);
    items.push(...page.items);
    cursor = page.nextCursor;
    if (cursor && visitedCursors.has(cursor)) {
      throw new Error("Asset pagination returned a repeated cursor.");
    }
    if (cursor) visitedCursors.add(cursor);
  } while (cursor);

  return items;
}

export function RuntimeAssetsPage() {
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const bindIntentKeys = useRef(new Map<string, string>());
  const unbindIntentKeys = useRef(new Map<string, string>());
  useProjectEvents(projectId);

  const assetsKey = ["projects", projectId, "asset-package"] as const;
  const assetsQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: async () => {
      const targetProjectId = projectId ?? "";
      const [slotsResult, assetPackageResult] = await Promise.allSettled([
        collectAssetPages((cursor) =>
          listProjectAssetSlots({ cursor, projectId: targetProjectId }),
        ),
        collectAssetPages((cursor) =>
          getProjectAssetPackage({ cursor, projectId: targetProjectId }),
        ),
      ]);
      let slots: ProjectAssetSlotDto[];
      let assetPackage: ProjectAssetSlotDto[];
      if (slotsResult.status === "fulfilled") {
        slots = slotsResult.value;
        assetPackage =
          assetPackageResult.status === "fulfilled" ? assetPackageResult.value : slotsResult.value;
      } else if (assetPackageResult.status === "fulfilled") {
        slots = assetPackageResult.value;
        assetPackage = assetPackageResult.value;
      } else {
        throw new AggregateError(
          [slotsResult.reason, assetPackageResult.reason],
          "Project assets could not be loaded.",
        );
      }
      return {
        assetPackage,
        partialRead: slotsResult.status === "rejected" || assetPackageResult.status === "rejected",
        slots,
      };
    },
    queryKey: assetsKey,
  });
  const refreshAssets = async () => {
    await queryClient.invalidateQueries({ exact: true, queryKey: assetsKey });
  };
  const bindMutation = useMutation({
    mutationFn: ({ idempotencyKey, input, slotId }: BindMutationIntent) =>
      bindProjectAsset({ idempotencyKey, input, slotId }),
    onSuccess: async (_binding, intent) => {
      if (bindIntentKeys.current.get(intent.signature) === intent.idempotencyKey) {
        bindIntentKeys.current.delete(intent.signature);
      }
      await refreshAssets();
    },
  });
  const unbindMutation = useMutation({
    mutationFn: ({ bindingId, idempotencyKey }: UnbindMutationIntent) =>
      unbindProjectAsset({ bindingId, idempotencyKey }),
    onSuccess: async (_binding, intent) => {
      if (unbindIntentKeys.current.get(intent.bindingId) === intent.idempotencyKey) {
        unbindIntentKeys.current.delete(intent.bindingId);
      }
      await refreshAssets();
    },
  });

  if (!projectId) return null;

  const fileAssetVersionId = searchParams.get("fileVersionId")?.trim();
  const sourceArtifactVersionId = searchParams.get("sourceArtifactVersionId")?.trim();
  const selectedAsset = fileAssetVersionId
    ? {
        fileAssetVersionId,
        label: (searchParams.get("assetLabel")?.trim() || "一个素材").slice(0, 80),
        sourceArtifactVersionId: sourceArtifactVersionId || undefined,
      }
    : undefined;
  const mutationError = bindMutation.error ?? unbindMutation.error;
  const errorMessage = mutationError
    ? runtimeErrorMessage(mutationError, "素材没有更新，请检查网络后重试。")
    : undefined;
  const writeReady = isCsrfTokenAvailable();
  let busyId: string | undefined;
  if (bindMutation.isPending) busyId = bindMutation.variables.slotId;
  else if (unbindMutation.isPending) busyId = unbindMutation.variables.bindingId;
  const bindAsset = (slotId: string, input: BindAssetRequest) => {
    const intent = { input, slotId };
    const signature = bindIntentSignature(intent);
    const idempotencyKey = bindIntentKeys.current.get(signature) ?? crypto.randomUUID();
    bindIntentKeys.current.set(signature, idempotencyKey);
    bindMutation.mutate({ ...intent, idempotencyKey, signature });
  };
  const unbindAsset = (bindingId: string) => {
    const idempotencyKey = unbindIntentKeys.current.get(bindingId) ?? crypto.randomUUID();
    unbindIntentKeys.current.set(bindingId, idempotencyKey);
    unbindMutation.mutate({ bindingId, idempotencyKey });
  };

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
        description="查看项目素材包、现有素材位置，并管理来自上传或生成结果的素材。"
        title="项目素材"
      />

      <div className="mt-5">
        {assetsQuery.isLoading ? (
          <div
            className="h-52 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
            role="status"
          >
            <span className="sr-only">正在读取项目素材</span>
          </div>
        ) : assetsQuery.isError ? (
          <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6">
            <p className="text-sm text-[var(--sh-danger)]" role="alert">
              {runtimeErrorMessage(assetsQuery.error, "项目素材暂时无法读取，请稍后重试。")}
            </p>
            <Button className="mt-4" onClick={() => void assetsQuery.refetch()} variant="secondary">
              重新读取素材
            </Button>
          </section>
        ) : (
          <>
            <p className="mb-4 text-sm text-[var(--sh-ink-muted)]" role="status">
              素材包包含 {String(assetsQuery.data?.assetPackage.length ?? 0)} 个素材位置。
            </p>
            {assetsQuery.data?.partialRead ? (
              <p
                className="mb-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm text-[var(--sh-warning)]"
                role="status"
              >
                部分素材信息未能更新，当前已保留成功读取的内容。请稍后刷新以完成对账。
              </p>
            ) : null}
            {!writeReady ? (
              <p
                className="mb-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm text-[var(--sh-warning)]"
                role="status"
              >
                当前会话仅支持查看素材，无法绑定或移除。
              </p>
            ) : null}
            <ProjectAssetSlotsPanel
              busyId={busyId}
              errorMessage={errorMessage}
              onBind={bindAsset}
              onUnbind={unbindAsset}
              selectedAsset={selectedAsset}
              slots={assetsQuery.data?.slots ?? []}
              writeDisabled={!writeReady || bindMutation.isPending || unbindMutation.isPending}
            />
          </>
        )}
      </div>
    </div>
  );
}
