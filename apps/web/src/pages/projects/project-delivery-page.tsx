import { useOutletContext } from "react-router";
import { Package, PackageCheck } from "lucide-react";
import type { ProjectOutletContext } from "@/layouts/project-layout";
import { useDelivery, useStartPackage } from "@/features/delivery";
import { DeliveryChecklist } from "@/features/delivery/DeliveryChecklist";
import { useProjectTasks } from "@/features/tasks";
import { Badge, Button, PageHeader, Progress, Skeleton, toast } from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

const DELIVERY_STATUS: Record<string, { label: string; tone: "neutral" | "brand" | "running" | "success" | "danger" }> = {
  not_ready: { label: "未就绪", tone: "neutral" },
  ready: { label: "可打包", tone: "brand" },
  packaging: { label: "打包中", tone: "running" },
  completed: { label: "已完成", tone: "success" },
  failed: { label: "打包失败", tone: "danger" },
};

/** 交付页：全项目交付清单 + 一键打包 + 打包进度与产物下载。 */
export function ProjectDeliveryPage() {
  const { project } = useOutletContext<ProjectOutletContext>();
  const delivery = useDelivery(project.project_id);
  const startPackage = useStartPackage(project.project_id);
  const tasks = useProjectTasks(project.project_id, {}, { refetchInterval: delivery.data?.status === "packaging" ? 2000 : undefined });

  const packageTask = (tasks.data ?? []).find((task) => task.task_id === delivery.data?.package_task_id);
  const status = DELIVERY_STATUS[delivery.data?.status ?? "not_ready"];

  return (
    <div className="space-y-4 p-6">
      <PageHeader
        title="交付"
        description="汇总每个课时的教案、PPT、视频与质量报告；全部就绪后打包为一个交付包。"
        actions={
          delivery.data ? (
            <>
              <Badge tone={status.tone}>{status.label}</Badge>
              <Button
                onClick={() =>
                  startPackage.mutate(undefined, {
                    onSuccess: () => toast({ tone: "info", title: "打包已开始", description: "完成后可在本页下载交付包。" }),
                  })
                }
                loading={startPackage.isPending}
                disabled={delivery.data.status !== "ready" && delivery.data.status !== "failed"}
                title={delivery.data.status === "not_ready" ? "先完成全部阻塞事项" : undefined}
              >
                {delivery.data.status === "completed" ? (
                  <>
                    <PackageCheck className="size-4" aria-hidden />
                    重新打包
                  </>
                ) : (
                  <>
                    <Package className="size-4" aria-hidden />
                    打包交付
                  </>
                )}
              </Button>
            </>
          ) : undefined
        }
      />

      {delivery.data?.status === "packaging" && packageTask ? (
        <div className="rounded-panel border border-line bg-surface-1 px-5 py-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-ink-1">正在打包交付物…</p>
            <span className="text-sm tabular-nums text-ink-2">{Math.round(packageTask.progress_percent)}%</span>
          </div>
          <Progress className="mt-2" value={packageTask.progress_percent} />
          <p className="mt-1.5 text-xs text-ink-muted">{packageTask.progress_message ?? ""}</p>
        </div>
      ) : null}

      {startPackage.isError ? <AppErrorPanel error={startPackage.error} title="打包发起失败" /> : null}

      {delivery.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-14" />
          ))}
        </div>
      ) : delivery.isError ? (
        <AppErrorPanel error={delivery.error} title="交付信息加载失败" onRetry={() => void delivery.refetch()} />
      ) : delivery.data ? (
        <DeliveryChecklist delivery={delivery.data} />
      ) : null}
    </div>
  );
}
