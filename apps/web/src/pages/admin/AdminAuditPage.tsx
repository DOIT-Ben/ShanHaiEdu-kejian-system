import { useAuditEvents } from "@/features/admin";
import { formatDateTime } from "@/shared/lib/format";
import { PageHeader, Panel, PanelBody, Skeleton } from "@/shared/ui";

/** 审计记录（04 §2.7）：谁在什么时间做了什么。 */
export default function AdminAuditPage() {
  const { data: events, isPending } = useAuditEvents();

  return (
    <div>
      <PageHeader title="审计记录" description="密钥变更、发布、删除等关键操作都会记录在这里。" />
      <Panel className="mt-6">
        <PanelBody className="p-0">
          {isPending ? (
            <div className="space-y-3 p-5">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-10 rounded-lg" />
              ))}
            </div>
          ) : (
            <ol className="divide-y divide-line-subtle">
              {(events ?? []).map((event) => (
                <li key={event.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-5 py-3.5 text-sm">
                  <span className="font-medium text-ink-strong">{event.actor_name}</span>
                  <span className="text-ink">{event.action}</span>
                  <span className="text-ink-muted">{event.resource_label}</span>
                  {event.detail ? <span className="w-full text-xs text-ink-faint">{event.detail}</span> : null}
                  <span className="ml-auto text-xs tabular-nums text-ink-faint">
                    {formatDateTime(event.occurred_at)}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
