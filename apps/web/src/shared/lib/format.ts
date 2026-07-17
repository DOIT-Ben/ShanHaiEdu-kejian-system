/**
 * 金额展示工具。
 * 金额一律使用后端返回的最小货币单位整数（minor units），
 * 前端只做展示换算，不做正式结算。
 */
export function formatMinorUnits(minorUnits: number | null | undefined, currency = "CNY"): string {
  if (minorUnits === null || minorUnits === undefined) return "—";
  const yuan = minorUnits / 100;
  const formatter = new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return formatter.format(yuan);
}

export function formatCostRange(
  minMinor: number | null | undefined,
  maxMinor: number | null | undefined,
  currency = "CNY",
): string {
  if (minMinor === null || minMinor === undefined || maxMinor === null || maxMinor === undefined) {
    return "费用待估算";
  }
  if (minMinor === maxMinor) return formatMinorUnits(minMinor, currency);
  return `${formatMinorUnits(minMinor, currency)} ~ ${formatMinorUnits(maxMinor, currency)}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatRelativeTime(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "—";
  const time = new Date(iso).getTime();
  if (Number.isNaN(time)) return "—";
  const diffMs = now - time;
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return formatDateTime(iso);
}

export function formatFileSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms}ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value)}%`;
}

/** 角色中文名。 */
export const ROLE_LABEL: Record<string, string> = {
  teacher: "教师",
  template_admin: "模板管理员",
  system_admin: "系统管理员",
  audit_admin: "审计管理员",
};
