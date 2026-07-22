import { CalendarDays, Download, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { getMockDraft, saveMockDraft } from "@/shared/api/mockClient";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { HorizontalScrollArea } from "@/shared/ui/HorizontalScrollArea";
import { Select } from "@/shared/ui/Select";

const AUDIT_FILTERS_KEY = "admin.audit-filters";
const MOCK_AUDIT_NOW = Date.parse("2026-07-17T12:00:00+08:00");

type AuditRecord = {
  action: string;
  object: string;
  user: string;
  time: string;
  occurredAt: string;
  result: string;
};

type AuditFilters = { query: string; actionType: string; rangeDays: 7 | 30 };

const records: AuditRecord[] = [
  {
    action: "批准教案",
    object: "认识百分数 · 第 1 课时",
    user: "林若晴",
    time: "今天 11:24",
    occurredAt: "2026-07-17T11:24:00+08:00",
    result: "成功",
  },
  {
    action: "修改内容要求",
    object: "PPT 第 3 页主视觉",
    user: "林若晴",
    time: "今天 11:02",
    occurredAt: "2026-07-17T11:02:00+08:00",
    result: "成功",
  },
  {
    action: "跨项目保存作品",
    object: "果汁标签插图",
    user: "林若晴",
    time: "今天 10:46",
    occurredAt: "2026-07-17T10:46:00+08:00",
    result: "成功",
  },
  {
    action: "发布内容包",
    object: "小学数学默认教案",
    user: "周晓舟",
    time: "昨天 16:18",
    occurredAt: "2026-07-16T16:18:00+08:00",
    result: "成功",
  },
  {
    action: "切换模型规则",
    object: "课堂视频能力",
    user: "陈明远",
    time: "昨天 15:51",
    occurredAt: "2026-07-16T15:51:00+08:00",
    result: "成功",
  },
  {
    action: "下载项目交付",
    object: "圆的认识 · 完整交付包",
    user: "林若晴",
    time: "7 月 2 日 14:03",
    occurredAt: "2026-07-02T14:03:00+08:00",
    result: "成功",
  },
];

function readFilters(): AuditFilters {
  return (
    getMockDraft<AuditFilters>(AUDIT_FILTERS_KEY)?.value ?? {
      query: "",
      actionType: "all",
      rangeDays: 30,
    }
  );
}

function escapeCsv(value: string) {
  return `"${value.replaceAll('"', '""')}"`;
}

function downloadAuditCsv(items: AuditRecord[]) {
  const rows = [
    ["操作", "对象", "成员", "时间", "结果"],
    ...items.map((record) => [
      record.action,
      record.object,
      record.user,
      record.occurredAt,
      record.result,
    ]),
  ];
  const csv = `\uFEFF${rows.map((row) => row.map(escapeCsv).join(",")).join("\r\n")}`;
  const link = document.createElement("a");
  link.href = `data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`;
  link.download = "审计记录.csv";
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
}

export function AdminAuditPage() {
  const [filters, setFilters] = useState(readFilters);
  const [selectedRecord, setSelectedRecord] = useState<AuditRecord | null>(null);
  const [message, setMessage] = useState("");
  const changeFilters = (next: AuditFilters) => {
    saveMockDraft(AUDIT_FILTERS_KEY, next);
    setFilters(next);
  };
  const visibleRecords = useMemo(() => {
    const keyword = filters.query.trim().toLowerCase();
    const cutoff = MOCK_AUDIT_NOW - filters.rangeDays * 24 * 60 * 60 * 1000;
    return records.filter((record) => {
      const queryMatched =
        !keyword ||
        [record.action, record.object, record.user].some((value) =>
          value.toLowerCase().includes(keyword),
        );
      const typeMatched =
        filters.actionType === "all" ||
        (filters.actionType === "publish" && record.action.includes("发布")) ||
        (filters.actionType === "approval" && /批准|驳回/.test(record.action)) ||
        (filters.actionType === "save" && record.action.includes("保存")) ||
        (filters.actionType === "download" && record.action.includes("下载"));
      return queryMatched && typeMatched && Date.parse(record.occurredAt) >= cutoff;
    });
  }, [filters]);
  return (
    <div className="p-5 md:p-6">
      <FocusPageHeader
        action={
          <Button
            onClick={() => {
              downloadAuditCsv(visibleRecords);
              setMessage(`已下载 ${String(visibleRecords.length)} 条审计记录`);
            }}
            variant="secondary"
          >
            <Download aria-hidden="true" />
            导出记录
          </Button>
        }
        description="记录内容发布、规则修改、批准驳回、跨项目保存、资产替换和下载。"
        title="审计记录"
      />
      <div className="mt-7 flex flex-wrap gap-3">
        <label className="flex min-w-64 flex-1 items-center gap-2 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3">
          <Search aria-hidden="true" className="size-4 text-[var(--sh-ink-faint)]" />
          <input
            aria-label="搜索审计记录"
            className="min-h-11 min-w-0 flex-1 outline-none"
            onChange={(event) => changeFilters({ ...filters, query: event.target.value })}
            placeholder="搜索操作、对象或成员"
            value={filters.query}
          />
        </label>
        <button
          className="inline-flex min-h-11 items-center gap-2 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-4 text-sm"
          onClick={() =>
            changeFilters({ ...filters, rangeDays: filters.rangeDays === 30 ? 7 : 30 })
          }
          type="button"
        >
          <CalendarDays aria-hidden="true" className="size-4" />
          最近 {filters.rangeDays} 天
        </button>
        <Select
          ariaLabel="操作类型"
          className="w-36"
          onValueChange={(actionType) => changeFilters({ ...filters, actionType })}
          options={[
            { label: "全部操作", value: "all" },
            { label: "内容发布", value: "publish" },
            { label: "批准与驳回", value: "approval" },
            { label: "作品保存", value: "save" },
            { label: "下载", value: "download" },
          ]}
          value={filters.actionType}
        />
      </div>
      <HorizontalScrollArea
        ariaLabel="审计记录列表"
        className="mt-5"
        hintTestId="admin-audit-table-scroll-next"
        viewportClassName="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]"
      >
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-[var(--sh-surface-soft)] text-xs text-[var(--sh-ink-muted)]">
            <tr>
              <th className="px-5 py-3">操作</th>
              <th className="px-5 py-3">对象</th>
              <th className="px-5 py-3">成员</th>
              <th className="px-5 py-3">时间</th>
              <th className="px-5 py-3">结果</th>
              <th className="px-5 py-3">详情</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--sh-line-subtle)]">
            {visibleRecords.map((record) => (
              <tr key={`${record.action}-${record.occurredAt}`}>
                <td className="px-5 py-4 font-semibold text-[var(--sh-ink-strong)]">
                  {record.action}
                </td>
                <td className="px-5 py-4">{record.object}</td>
                <td className="px-5 py-4 text-[var(--sh-ink-muted)]">{record.user}</td>
                <td className="px-5 py-4 text-[var(--sh-ink-muted)]">{record.time}</td>
                <td className="px-5 py-4 font-semibold text-[var(--sh-success)]">
                  {record.result}
                </td>
                <td className="px-5 py-4">
                  <button
                    className="font-semibold text-[var(--sh-brand-600)]"
                    onClick={() => setSelectedRecord(record)}
                    type="button"
                  >
                    查看
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </HorizontalScrollArea>
      {visibleRecords.length === 0 ? (
        <p className="mt-5 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-4 text-sm text-[var(--sh-ink-muted)]">
          当前筛选条件下没有审计记录。
        </p>
      ) : null}
      {selectedRecord ? (
        <section className="mt-5 rounded-[var(--sh-radius-md)] border border-[var(--sh-brand-100)] bg-[var(--sh-surface-elevated)] p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-[var(--sh-brand-600)]">
                {selectedRecord.time}
              </p>
              <h2 className="mt-1 text-lg font-bold text-[var(--sh-ink-strong)]">操作详情</h2>
            </div>
            <Button onClick={() => setSelectedRecord(null)} size="sm" variant="quiet">
              关闭
            </Button>
          </div>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-[var(--sh-ink-muted)]">操作</dt>
              <dd className="mt-1 font-semibold">{selectedRecord.action}</dd>
            </div>
            <div>
              <dt className="text-[var(--sh-ink-muted)]">对象</dt>
              <dd className="mt-1 font-semibold">{selectedRecord.object}</dd>
            </div>
            <div>
              <dt className="text-[var(--sh-ink-muted)]">成员</dt>
              <dd className="mt-1 font-semibold">{selectedRecord.user}</dd>
            </div>
            <div>
              <dt className="text-[var(--sh-ink-muted)]">结果</dt>
              <dd className="mt-1 font-semibold text-[var(--sh-success)]">
                {selectedRecord.result}
              </dd>
            </div>
          </dl>
        </section>
      ) : null}
      {message ? (
        <p aria-live="polite" className="mt-3 text-sm font-semibold text-[var(--sh-brand-700)]">
          {message}
        </p>
      ) : null}
    </div>
  );
}
