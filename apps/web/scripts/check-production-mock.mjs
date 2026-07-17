/**
 * 生产 Mock 排除检查：
 * 1. dist 中不允许存在 mockServiceWorker.js。
 * 2. 打包产物中不允许出现 MSW 运行时特征字符串。
 */
import { readdirSync, readFileSync, existsSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const dist = resolve(process.cwd(), "dist");
if (!existsSync(dist)) {
  console.error("[check:mock-exclusion] dist/ 不存在，请先运行 pnpm build");
  process.exit(1);
}

if (existsSync(join(dist, "mockServiceWorker.js"))) {
  console.error("[check:mock-exclusion] 失败：dist/mockServiceWorker.js 出现在生产构建中");
  process.exit(1);
}

const markers = ["mockServiceWorker", "[MSW]", "msw/browser"];
const offenders = [];

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      walk(full);
      continue;
    }
    if (!/\.(js|css|html)$/.test(name)) continue;
    const content = readFileSync(full, "utf8");
    for (const marker of markers) {
      if (content.includes(marker)) offenders.push(`${full} -> ${marker}`);
    }
  }
}
walk(dist);

if (offenders.length > 0) {
  console.error("[check:mock-exclusion] 失败：生产构建包含 Mock 特征：");
  for (const line of offenders) console.error("  " + line);
  process.exit(1);
}

console.log("[check:mock-exclusion] 通过：生产构建不包含 MSW。");
