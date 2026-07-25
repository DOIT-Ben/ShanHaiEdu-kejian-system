import { expect, test, type Page } from "@playwright/test";

function requiredEnvironment(name: string) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const accessCode = requiredEnvironment("SHANHAI_E2E_ACCESS_CODE");
const apiBaseUrl = process.env.SHANHAI_E2E_API_BASE_URL ?? "http://127.0.0.1:58080/api/v2";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("学校访问码").fill(accessCode);
  await page.getByRole("button", { name: "登录" }).click();
  await expect(page).toHaveURL(/\/app\/projects$/);
}

test("teacher_completes_exact_lesson_plan_rescue_with_real_api", async ({ page }) => {
  test.setTimeout(120_000);
  await login(page);
  await page.getByRole("link", { name: "继续制作十二部分教案验收" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "十二部分教案验收" })).toBeVisible();

  const firstLesson = page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name: "1～5的认识" }) });
  await firstLesson.getByRole("link", { name: "查看教案" }).click();
  const firstLessonUrl = page.url();
  const firstLessonId = /\/lessons\/([0-9a-f-]+)\/work/.exec(firstLessonUrl)?.[1];
  const projectId = /\/projects\/([0-9a-f-]+)\/lessons/.exec(firstLessonUrl)?.[1];
  if (!firstLessonId || !projectId) throw new Error("Lesson workbench URL is missing exact IDs");
  expect(firstLessonId).toBeTruthy();
  expect(projectId).toBeTruthy();

  const startedResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v2\/node-runs\/[0-9a-f-]+\/start$/.test(response.url()),
  );
  await page.getByRole("button", { name: "生成十二部分教案" }).click();
  const accepted = (await (await startedResponse).json()) as { data: { job_id: string } };
  await expect(page.getByRole("progressbar", { name: /任务进度/ })).toBeVisible();
  await expect(page.getByText("Lesson-plan generation completed")).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByLabel(/^一、教学内容 课题 \d+$/)).toBeVisible();

  const generatedJob = await page.evaluate(
    async ({ baseUrl, jobId }) => {
      const response = await fetch(`${baseUrl}/generation-jobs/${jobId}`, {
        credentials: "include",
      });
      return (await response.json()) as {
        data: {
          lesson_unit_id: string;
          result_artifact_version_id: string;
          status: string;
        };
      };
    },
    { baseUrl: apiBaseUrl, jobId: accepted.data.job_id },
  );
  expect(generatedJob.data.status).toBe("succeeded");
  expect(generatedJob.data.lesson_unit_id).toBe(firstLessonId);
  expect(generatedJob.data.result_artifact_version_id).toBeTruthy();

  const topic = page.getByLabel(/^一、教学内容 课题 \d+$/);
  await topic.fill("教师编辑后的十二部分教案");
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
        .endsWith(`/lesson-plan/artifact-versions/${submitted.data.id}/quality-validations`),
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
  await expect(page.getByLabel(/^一、教学内容 课题 \d+$/)).toHaveValue("教师编辑后的十二部分教案");
  await expect(page.getByText(/已批准版本/)).toBeVisible();

  await page.getByRole("link", { name: "返回项目" }).click();
  const secondLesson = page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name: "第二课时隔离验证" }) });
  await secondLesson.getByRole("link", { name: "查看教案" }).click();
  const secondLessonId = /\/lessons\/([0-9a-f-]+)\/work/.exec(page.url())?.[1];
  if (!secondLessonId) throw new Error("Second lesson workbench URL is missing its exact ID");
  expect(secondLessonId).toBeTruthy();
  expect(secondLessonId).not.toBe(firstLessonId);
  await expect(page.getByText("生成完成后，十二部分教案会显示在这里。")).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveCount(0);

  const secondFacts = await page.evaluate(
    async ({ baseUrl, lessonId, projectId: exactProjectId }) => {
      const [artifactResponse, jobsResponse] = await Promise.all([
        fetch(`${baseUrl}/projects/${exactProjectId}/lessons/${lessonId}/lesson-plan/artifact`, {
          credentials: "include",
        }),
        fetch(
          `${baseUrl}/projects/${exactProjectId}/lessons/${lessonId}/lesson-plan/generation-jobs`,
          { credentials: "include" },
        ),
      ]);
      return {
        artifact: (await artifactResponse.json()) as { data: { artifact: unknown } },
        jobs: (await jobsResponse.json()) as { data: { items: unknown[] } },
      };
    },
    { baseUrl: apiBaseUrl, lessonId: secondLessonId, projectId },
  );
  expect(secondFacts.artifact.data.artifact).toBeNull();
  expect(secondFacts.jobs.data.items).toEqual([]);

  const session = await page.evaluate(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/auth/session`, { credentials: "include" });
    return (await response.json()) as { data: { csrf_token: string } };
  }, apiBaseUrl);
  await page.getByRole("button", { name: "打开个人菜单" }).click();
  await page.getByRole("menuitem", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login$/);
  const rejected = await page.evaluate(
    async ({ baseUrl, csrfToken }) => {
      const response = await fetch(`${baseUrl}/projects`, {
        body: JSON.stringify({ knowledge_point: "登出后拒绝", title: "登出后拒绝" }),
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": "r1-rescue-logout-write",
          "X-CSRF-Token": csrfToken,
        },
        method: "POST",
      });
      return response.status;
    },
    { baseUrl: apiBaseUrl, csrfToken: session.data.csrf_token },
  );
  expect(rejected).toBe(401);
});
