import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const distDirectory = resolve(process.cwd(), "dist");
const forbiddenFile = "mockServiceWorker.js";
const textAssetExtensions = new Set([".css", ".html", ".js", ".json", ".svg"]);
const forbiddenTexts = [
  { label: "MSW Worker", pattern: /(?:mockServiceWorker|setupWorker)/ },
  {
    label: "Mock Runtime",
    pattern: /(?:shanhaiedu\.mock-runtime\.v1|MOCK_INVALID_CREDENTIALS|mock-session-)/,
  },
  {
    label: "开发演示凭据",
    pattern: /(?:teacher-demo|admin-demo|lin\.teacher@example\.edu|admin@example\.edu)/,
  },
  {
    label: "Runtime 合同测试入口",
    pattern: /(?:runtime-contract-test|VITE_RUNTIME_CONTRACT_TEST)/,
  },
];

if (!existsSync(distDirectory)) {
  console.error("构建目录不存在：请先运行 pnpm build");
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
const unresolvedAssetReferences = new Map();
const forbiddenContents = files.flatMap((path) => {
  try {
    const content = readFileSync(path, "utf8");
    const extension = path.slice(path.lastIndexOf("."));
    if (textAssetExtensions.has(extension)) {
      for (const [assetReference] of content.matchAll(/\/assets\/[A-Za-z0-9._~@%+/-]+/g)) {
        const assetPath = assetReference.split(/[?#]/, 1)[0];
        const outputPath = resolve(distDirectory, `.${assetPath}`);
        if (!existsSync(outputPath)) {
          const sources = unresolvedAssetReferences.get(assetPath) ?? new Set();
          sources.add(relative(distDirectory, path));
          unresolvedAssetReferences.set(assetPath, sources);
        }
      }
    }
    return forbiddenTexts
      .filter(({ pattern }) => pattern.test(content))
      .map(({ label }) => ({ label, path }));
  } catch {
    return [];
  }
});

if (forbiddenPaths.length || forbiddenContents.length || unresolvedAssetReferences.size) {
  console.error("构建产物边界检查失败：");
  for (const path of forbiddenPaths) {
    console.error(`- MSW Worker: ${relative(distDirectory, path)}`);
  }
  for (const { label, path } of forbiddenContents) {
    console.error(`- ${label}: ${relative(distDirectory, path)}`);
  }
  for (const [assetPath, sources] of unresolvedAssetReferences) {
    console.error(`- 缺失静态素材: ${assetPath}（引用自 ${[...sources].join("、")}）`);
  }
  process.exit(1);
}

console.log(
  `构建边界检查通过：${files.length} 个文件不含 MSW Worker、开发演示凭据或缺失静态素材；此检查不代表真实认证与 API 联调已经完成`,
);
