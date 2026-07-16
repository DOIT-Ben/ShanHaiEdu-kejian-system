import { Package } from "lucide-react";
import { useDelivery } from "@/features/delivery";
import { DeliveryChecklist } from "@/features/delivery/DeliveryChecklist";
import { Skeleton } from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";
import type { CanvasProps } from "../registry";

/** 交付确认画布：本课时的交付清单（项目级打包在「交付」页完成）。 */
export function DeliveryCanvas({ projectId, lessonId }: CanvasProps) {
  const delivery = useDelivery(projectId, lessonId);
  if (delivery.isPending) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-14" />
        ))}
      </div>
    );
  }
  if (delivery.isError) {
    return <AppErrorPanel error={delivery.error} title="交付信息加载失败" onRetry={() => void delivery.refetch()} />;
  }
  return (
    <div className="space-y-3">
      <p className="flex items-center gap-2 text-sm text-ink-2">
        <Package className="size-4 text-brand" aria-hidden />
        本课时的交付物就绪情况；全部就绪后，在项目「交付」页可一键打包下载。
      </p>
      <DeliveryChecklist delivery={delivery.data} />
    </div>
  );
}
