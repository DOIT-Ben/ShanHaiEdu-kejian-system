import { tmpdir } from "node:os";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";

function requiredEnvironment(name: string) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const accessCode = requiredEnvironment("SHANHAI_E2E_ACCESS_CODE");
const apiBaseUrl = process.env.SHANHAI_E2E_API_BASE_URL ?? "http://127.0.0.1:58080/api/v2";
const realProviderMode = process.env.SHANHAI_R1_WORKER_MODE === "real";
const generationTimeout = realProviderMode ? 300_000 : 60_000;

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("学校访问码").fill(accessCode);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/projects$/);
}

test("teacher_completes_exact_material_scope_and_lesson_division_with_real_api", async ({
  page,
}) => {
  test.setTimeout(realProviderMode ? 900_000 : 180_000);
  await login(page);
  await page.getByRole("link", { name: "继续制作教材范围与课时划分验收" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "教材范围与课时划分验收" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "教材与解析" }).click();
  await page
    .getByLabel("选择教材 PDF")
    .setInputFiles(join(tmpdir(), "shanhai-r1-e2e-textbook.pdf"));
  const confirmationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v2\/projects\/[0-9a-f-]+\/materials\/[0-9a-f-]+\/confirm$/.test(response.url()),
  );
  await page.getByRole("button", { name: "上传并解析教材" }).click();
  const parseJob = (await (await confirmationResponse).json()) as { data: { job_id: string } };
  await expect(page).toHaveURL(/\/setup\?jobId=[0-9a-f-]+&materialId=[0-9a-f-]+$/);
  await expect(page.getByRole("progressbar", { name: "教材处理进度 100%" })).toBeVisible({
    timeout: 60_000,
  });
  expect(page.url()).toContain(`jobId=${parseJob.data.job_id}`);
  await page.getByRole("link", { name: "查看教材详情" }).click();

  const routeIds = /\/projects\/([0-9a-f-]+)\/materials\/([0-9a-f-]+)/.exec(page.url());
  if (!routeIds) throw new Error("Material page URL is missing exact project and material IDs");
  const projectId = routeIds[1];
  const materialId = routeIds[2];
  if (!projectId || !materialId) {
    throw new Error("Material page URL contains incomplete project or material IDs");
  }
  await expect(page.getByRole("heading", { name: "物理页 2" })).toBeVisible();
  await expect(page.getByText("R1 evidence page 2")).toBeVisible();

  await page.getByLabel("起始物理页").fill("2");
  await page.getByLabel("结束物理页").fill("2");
  const scopeResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/projects/${projectId}/material-scope/versions`),
  );
  await page.getByRole("button", { name: "保存教材范围" }).click();
  const scope = (await (await scopeResponse).json()) as {
    data: { current_submitted_version: { id: string } };
  };
  const scopeVersionId = scope.data.current_submitted_version.id;
  await expect(page.getByText(/物理页 2 至 2，等待教师确认/)).toBeVisible();

  const scopeApprovalResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/artifact-versions/${scopeVersionId}/approvals`),
  );
  await page.getByRole("button", { name: "确认当前范围" }).click();
  expect((await scopeApprovalResponse).status()).toBe(201);
  await expect(page.getByText(/物理页 2 至 2，教师已确认/)).toBeVisible();

  const divisionStartResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v2\/node-runs\/[0-9a-f-]+\/start$/.test(response.url()),
  );
  await page.getByRole("button", { name: "生成课时划分" }).click();
  const accepted = (await (await divisionStartResponse).json()) as { data: { job_id: string } };
  await expect(page.getByRole("progressbar", { name: /任务进度/ })).toHaveAttribute(
    "aria-valuenow",
    /^(?:0|[1-9]\d?|100)$/,
    { timeout: generationTimeout },
  );
  await expect(page.getByRole("progressbar", { name: "任务进度 100%" })).toBeVisible({
    timeout: generationTimeout,
  });
  await expect(page.getByLabel("课题名称")).toBeVisible();

  const generatedJob = await page.evaluate(
    async ({ baseUrl, jobId }) => {
      const response = await fetch(`${baseUrl}/generation-jobs/${jobId}`, {
        credentials: "include",
      });
      return (await response.json()) as {
        data: { project_id: string; result_artifact_version_id: string; status: string };
      };
    },
    { baseUrl: apiBaseUrl, jobId: accepted.data.job_id },
  );
  expect(generatedJob.data.project_id).toBe(projectId);
  expect(generatedJob.data.status).toBe("succeeded");
  expect(generatedJob.data.result_artifact_version_id).toBeTruthy();

  await page.getByLabel("课题名称").fill("1～5的认识（教师修订）");
  const saveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      /\/api\/v2\/artifacts\/[0-9a-f-]+\/drafts\/main$/.test(response.url()),
  );
  await page.getByRole("button", { name: "保存草稿" }).click();
  expect((await saveResponse).ok()).toBe(true);

  const submitResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v2\/artifacts\/[0-9a-f-]+\/versions$/.test(response.url()),
  );
  await page.getByRole("button", { name: "提交当前草稿" }).click();
  const submitted = (await (await submitResponse).json()) as { data: { id: string } };

  const qualityResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response
        .url()
        .endsWith(`/lesson-division/artifact-versions/${submitted.data.id}/quality-validations`),
  );
  await page.getByRole("button", { name: "运行质量检查" }).click();
  expect((await qualityResponse).status()).toBe(202);
  await expect(page.getByText("检查通过，可以批准当前版本")).toBeVisible({
    timeout: 60_000,
  });

  const approvalResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/artifact-versions/${submitted.data.id}/approvals`),
  );
  await page.getByRole("button", { name: "批准当前版本" }).click();
  const approved = (await (await approvalResponse).json()) as {
    data: { artifact_version_id: string };
  };
  expect(approved.data.artifact_version_id).toBe(submitted.data.id);
  await expect(page.getByText(/已批准版本/)).toBeVisible();

  await page.reload();
  await expect(page.getByLabel("课题名称")).toHaveValue("1～5的认识（教师修订）");
  await expect(page.getByText(/已批准版本/)).toBeVisible();

  const isolationFacts = await page.evaluate(
    async ({ baseUrl, exactMaterialId }) => {
      const projectsResponse = await fetch(`${baseUrl}/projects?page%5Blimit%5D=100`, {
        credentials: "include",
      });
      const projects = (await projectsResponse.json()) as {
        data: { items: Array<{ id: string; title: string }> };
      };
      const isolationProject = projects.data.items.find(
        (project) => project.title === "教材范围隔离验收",
      );
      if (!isolationProject) throw new Error("Isolation project fixture is missing");
      const projectId = isolationProject.id;
      const [materialsResponse, scopeResponse, jobsResponse, divisionResponse] = await Promise.all([
        fetch(`${baseUrl}/projects/${projectId}/materials`, { credentials: "include" }),
        fetch(`${baseUrl}/projects/${projectId}/material-scope/artifact`, {
          credentials: "include",
        }),
        fetch(`${baseUrl}/projects/${projectId}/lesson-division/generation-jobs`, {
          credentials: "include",
        }),
        fetch(`${baseUrl}/projects/${projectId}/lesson-division/artifact`, {
          credentials: "include",
        }),
      ]);
      const materials = (await materialsResponse.json()) as {
        data: { items: Array<{ id: string }> };
      };
      const scope = (await scopeResponse.json()) as { data: { artifact: unknown } };
      const jobs = (await jobsResponse.json()) as { data: { items: unknown[] } };
      const division = (await divisionResponse.json()) as { data: { artifact: unknown } };
      return {
        division: division.data.artifact,
        jobs: jobs.data.items,
        materialIds: materials.data.items.map((item) => item.id),
        scope: scope.data.artifact,
        sourceMaterialLeaked: materials.data.items.some((item) => item.id === exactMaterialId),
      };
    },
    { baseUrl: apiBaseUrl, exactMaterialId: materialId },
  );
  expect(isolationFacts.materialIds).toHaveLength(0);
  expect(isolationFacts.sourceMaterialLeaked).toBe(false);
  expect(isolationFacts.scope).toBeNull();
  expect(isolationFacts.jobs).toEqual([]);
  expect(isolationFacts.division).toBeNull();

  const session = await page.evaluate(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/auth/session`, { credentials: "include" });
    return (await response.json()) as { data: { csrf_token: string } };
  }, apiBaseUrl);
  await page.getByRole("button", { name: "打开个人菜单" }).click();
  await page.getByRole("menuitem", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login$/);
  const rejected = await page.evaluate(
    async ({ baseUrl, csrfToken, exactProjectId, exactScopeVersionId }) => {
      const response = await fetch(
        `${baseUrl}/projects/${exactProjectId}/lesson-division/node-runs`,
        {
          body: JSON.stringify({ material_scope_artifact_version_id: exactScopeVersionId }),
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": "r1-division-logout-write",
            "X-CSRF-Token": csrfToken,
          },
          method: "POST",
        },
      );
      return response.status;
    },
    {
      baseUrl: apiBaseUrl,
      csrfToken: session.data.csrf_token,
      exactProjectId: projectId,
      exactScopeVersionId: scopeVersionId,
    },
  );
  expect(rejected).toBe(401);
});
