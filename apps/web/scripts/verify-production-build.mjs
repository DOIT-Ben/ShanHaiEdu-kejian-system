import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const distDirectory = resolve(process.cwd(), "dist");
const forbiddenFile = "mockServiceWorker.js";
const forbiddenTexts = [
  { label: "MSW Worker", pattern: /(?:mockServiceWorker|setupWorker)/ },
  {
    label: "开发演示凭据",
    pattern: /(?:teacher-demo|admin-demo|lin\.teacher@example\.edu|admin@example\.edu)/,
  },
];

if (!existsSync(distDirectory)) {
  console.error("构建目录不存在：请先运行 npm run build");
  process.exit(1);
}

const files = [];
function collect(directory) {
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) collect(path);
    else files.push(path);
  }
}
collect(distDirectory);

const forbiddenPaths = files.filter((path) => path.endsWith(forbiddenFile));
const forbiddenContents = files.flatMap((path) => {
  try {
    const content = readFileSync(path, "utf8");
    return forbiddenTexts
      .filter(({ pattern }) => pattern.test(content))
      .map(({ label }) => ({ label, path }));
  } catch {
    return [];
  }
});

if (forbiddenPaths.length || forbiddenContents.length) {
  console.error("构建产物包含禁止发布的开发内容：");
  for (const path of forbiddenPaths) {
    console.error(`- MSW Worker: ${relative(distDirectory, path)}`);
  }
  for (const { label, path } of forbiddenContents) {
    console.error(`- ${label}: ${relative(distDirectory, path)}`);
  }
  process.exit(1);
}

console.log(
  `构建边界检查通过：${files.length} 个文件不含 MSW Worker 或开发演示凭据；此检查不代表真实认证与 API 联调已经完成`,
);
