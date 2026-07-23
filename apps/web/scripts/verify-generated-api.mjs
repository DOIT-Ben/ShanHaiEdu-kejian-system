import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const repositoryRoot = fileURLToPath(new URL("../../..", import.meta.url));
const generatedPaths = ["contracts/generated", "apps/web/src/generated"];
const result = spawnSync(
  "git",
  ["status", "--porcelain=v1", "--untracked-files=all", "--", ...generatedPaths],
  {
    cwd: repositoryRoot,
    encoding: "utf8",
  },
);

if (result.error || result.status !== 0) {
  console.error("无法检查 OpenAPI 生成物是否漂移。", result.error?.message ?? result.stderr);
  process.exit(1);
}

if (result.stdout.trim()) {
  console.error("OpenAPI 生成物存在未提交漂移：");
  console.error(result.stdout.trimEnd());
  process.exit(1);
}

console.log("OpenAPI 生成物无漂移。");
