import { describe, expect, it } from "vitest";
import {
  formatDuration,
  formatFileSize,
  formatMinorUnits,
  formatCostRange,
  formatPercent,
  formatRelativeTime,
} from "./format";

describe("formatMinorUnits", () => {
  it("以元显示分单位金额", () => {
    expect(formatMinorUnits(12345)).toContain("123.45");
    expect(formatMinorUnits(0)).toContain("0.00");
  });
  it("空值显示占位符", () => {
    expect(formatMinorUnits(null)).toBe("—");
    expect(formatMinorUnits(undefined)).toBe("—");
  });
});

describe("formatCostRange", () => {
  it("区间显示上下限", () => {
    const range = formatCostRange(1000, 2000);
    expect(range).toContain("10.00");
    expect(range).toContain("20.00");
    expect(range).toContain("~");
  });
  it("上下限相同则只显示一个值", () => {
    expect(formatCostRange(1000, 1000)).not.toContain("~");
  });
  it("缺失时提示待估算", () => {
    expect(formatCostRange(null, 2000)).toBe("费用待估算");
  });
});

describe("formatFileSize", () => {
  it("按量级换算", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(2048)).toBe("2.0 KB");
    expect(formatFileSize(3 * 1024 * 1024)).toBe("3.0 MB");
  });
});

describe("formatDuration", () => {
  it("毫秒转可读时长", () => {
    expect(formatDuration(500)).toBe("500ms");
    expect(formatDuration(1500)).toBe("1.5s");
    expect(formatDuration(65_000)).toBe("1m 5s");
  });
});

describe("formatPercent", () => {
  it("保留整数百分比", () => {
    expect(formatPercent(66.6)).toBe("67%");
    expect(formatPercent(null)).toBe("—");
  });
});

describe("formatRelativeTime", () => {
  it("近期时间显示相对描述", () => {
    const now = Date.now();
    expect(formatRelativeTime(new Date(now - 30_000).toISOString(), now)).toBe("刚刚");
    expect(formatRelativeTime(new Date(now - 5 * 60_000).toISOString(), now)).toBe("5 分钟前");
    expect(formatRelativeTime(new Date(now - 3 * 3600_000).toISOString(), now)).toBe("3 小时前");
    expect(formatRelativeTime(new Date(now - 2 * 86_400_000).toISOString(), now)).toBe("2 天前");
  });
  it("无效输入显示占位符", () => {
    expect(formatRelativeTime(null)).toBe("—");
    expect(formatRelativeTime("not-a-date")).toBe("—");
  });
});
