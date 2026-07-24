import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const repositoryRoot = fileURLToPath(new URL("../../..", import.meta.url));
const generatedPaths = ["contracts/generated", "apps/web/src/generated"];
const diffResult = spawnSync("git", ["diff", "--name-only", "HEAD", "--", ...generatedPaths], {
  cwd: repositoryRoot,
  encoding: "utf8",
});
const untrackedResult = spawnSync("git", ["ls-files", "--others", "--", ...generatedPaths], {
  cwd: repositoryRoot,
  encoding: "utf8",
});

if (
  diffResult.error ||
  diffResult.status !== 0 ||
  untrackedResult.error ||
  untrackedResult.status !== 0
) {
  const details =
    diffResult.error?.message ??
    untrackedResult.error?.message ??
    diffResult.stderr ??
    untrackedResult.stderr;
  console.error("无法检查 OpenAPI 生成物是否漂移。", details);
  process.exit(1);
}

const changedPaths = [diffResult.stdout.trim(), untrackedResult.stdout.trim()]
  .filter(Boolean)
  .join("\n");

if (changedPaths) {
  console.error("OpenAPI 生成物存在未提交漂移：");
  console.error(changedPaths);
  process.exit(1);
}

console.log("OpenAPI 生成物无漂移。");
