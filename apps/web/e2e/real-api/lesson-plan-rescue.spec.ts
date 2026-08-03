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

async function expectGenerationProgress(page: Page) {
  await expect(page.getByRole("progressbar", { name: /任务进度/ })).toHaveAttribute(
    "aria-valuenow",
    /^(?:0|[1-9]\d?|100)$/,
    { timeout: generationTimeout },
  );
}

type GenerationJobFacts = {
  error_code: string | null;
  lesson_unit_id: string | null;
  result_artifact_version_id: string | null;
  status: string;
  workflow_node_key: string | null;
};

async function getGenerationJob(page: Page, jobId: string) {
  return page.evaluate(
    async ({ baseUrl, exactJobId }) => {
      const response = await fetch(`${baseUrl}/generation-jobs/${exactJobId}`, {
        credentials: "include",
      });
      const body = (await response.json()) as { data: GenerationJobFacts };
      return body.data;
    },
    { baseUrl: apiBaseUrl, exactJobId: jobId },
  );
}

async function waitForTerminalJob(page: Page, jobId: string) {
  await expect
    .poll(async () => (await getGenerationJob(page, jobId)).status, {
      timeout: generationTimeout,
    })
    .toMatch(/^(?:succeeded|failed|cancelled)$/);
  return getGenerationJob(page, jobId);
}

test("teacher_completes_exact_lesson_plan_rescue_with_real_api", async ({ page }) => {
  test.setTimeout(realProviderMode ? 900_000 : 180_000);
  await login(page);
  await page.getByRole("link", { name: "继续制作十二部分教案验收" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "十二部分教案验收" })).toBeVisible();

  await page.getByRole("link", { name: "教材与解析" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "教材与课时划分" })).toBeVisible();
  await page.getByRole("link").filter({ hasText: "issue-125-material.pdf" }).click();
  await expect(page.getByText(/已保存范围：物理页 .*教师已确认/)).toBeVisible();
  await expect(page.getByRole("region", { name: "课时划分" })).toBeVisible();
  const lessonTitles = page.getByLabel("课题名称");
  await expect(lessonTitles).toHaveCount(2);
  await expect(lessonTitles.nth(0)).toHaveValue("1～5的认识");
  await expect(lessonTitles.nth(1)).toHaveValue("第二课时隔离验证");
  await expect(page.getByText(/已批准版本/)).toBeVisible();
  await page.getByRole("link", { name: "返回项目" }).click();
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
  await expectGenerationProgress(page);
  await expect(page.getByText("Lesson-plan generation completed")).toBeVisible({
    timeout: generationTimeout,
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

  await page.getByRole("link", { name: /课堂导入/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "1～5的认识" })).toBeVisible();
  await expect(page.getByRole("link", { name: /课堂导入/ })).toHaveAttribute(
    "aria-current",
    "step",
  );
  const introStartResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v2\/node-runs\/[0-9a-f-]+\/start$/.test(response.url()),
  );
  await page.getByRole("button", { name: "生成三类九套" }).click();
  let introAccepted = (await (await introStartResponse).json()) as { data: { job_id: string } };
  await expectGenerationProgress(page);
  let introJob = await waitForTerminalJob(page, introAccepted.data.job_id);
  if (realProviderMode && introJob.status === "failed" && introJob.error_code === "MODEL_TIMEOUT") {
    const retryStartResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        /\/api\/v2\/node-runs\/[0-9a-f-]+\/start$/.test(response.url()),
    );
    const retryButton = page.getByRole("button", { name: "生成三类九套" });
    await expect(retryButton).toBeEnabled();
    await retryButton.click();
    introAccepted = (await (await retryStartResponse).json()) as { data: { job_id: string } };
    await expectGenerationProgress(page);
    introJob = await waitForTerminalJob(page, introAccepted.data.job_id);
  }
  expect(introJob.status).toBe("succeeded");
  await expect(page.getByText("Intro-options generation completed")).toBeVisible({
    timeout: generationTimeout,
  });
  const introBody = page.getByLabel("方案正文").first();
  await expect(introBody).toBeVisible();

  expect(introJob.workflow_node_key).toBe("intro.generate_options");
  expect(introJob.lesson_unit_id).toBe(firstLessonId);
  expect(introJob.result_artifact_version_id).toBeTruthy();

  await introBody.fill("教师编辑后的课堂导入方案正文");
  const introSaveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      /\/api\/v2\/artifacts\/[0-9a-f-]+\/drafts\/main$/.test(response.url()),
  );
  await page.getByRole("button", { name: "保存草稿" }).click();
  expect((await introSaveResponse).ok()).toBe(true);

  const introSubmitResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v2\/artifacts\/[0-9a-f-]+\/versions$/.test(response.url()),
  );
  await page.getByRole("button", { name: "提交当前草稿" }).click();
  const introSubmitted = (await (await introSubmitResponse).json()) as { data: { id: string } };

  const introQualityResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response
        .url()
        .endsWith(`/intro-options/artifact-versions/${introSubmitted.data.id}/quality-validations`),
  );
  await page.getByRole("button", { name: "运行质量检查" }).click();
  expect((await introQualityResponse).status()).toBe(202);
  await expect(page.getByText("检查通过，可以批准当前版本")).toBeVisible({
    timeout: 60_000,
  });

  const introApprovalResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/artifact-versions/${introSubmitted.data.id}/approvals`),
  );
  await page.getByRole("button", { name: "批准当前版本" }).click();
  const introApproved = (await (await introApprovalResponse).json()) as {
    data: { artifact_version_id: string };
  };
  expect(introApproved.data.artifact_version_id).toBe(introSubmitted.data.id);

  const selectionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/lessons/${firstLessonId}/intro-selections`),
  );
  await page.getByRole("button", { name: "采用本方案" }).first().click();
  const selection = (await (await selectionResponse).json()) as {
    data: { artifact_version_id: string; option_key: string };
  };
  expect(selection.data.artifact_version_id).toBe(introSubmitted.data.id);
  expect(selection.data.option_key).toBeTruthy();

  await page.reload();
  await expect(page.getByLabel("方案正文").first()).toHaveValue("教师编辑后的课堂导入方案正文");
  await expect(page.getByText("已采用", { exact: true })).toBeVisible();
  const restoredIntro = await page.evaluate(
    async ({ baseUrl, lessonId }) => {
      const response = await fetch(`${baseUrl}/lessons/${lessonId}/intro-options`, {
        credentials: "include",
      });
      return (await response.json()) as {
        data: {
          current_approved_version_id: string;
          current_selection: { artifact_version_id: string; option_key: string };
        };
      };
    },
    { baseUrl: apiBaseUrl, lessonId: firstLessonId },
  );
  expect(restoredIntro.data.current_approved_version_id).toBe(introSubmitted.data.id);
  expect(restoredIntro.data.current_selection.artifact_version_id).toBe(introSubmitted.data.id);
  expect(restoredIntro.data.current_selection.option_key).toBe(selection.data.option_key);

  await page.getByRole("link", { name: "课堂视频" }).click();
  await expect(page.getByRole("heading", { name: "6 秒黄金切片" })).toBeVisible();
  await expect(page.getByText("课堂导入已采用")).toBeVisible();
  await expect(page.getByText("正式关键帧已绑定")).toBeVisible();
  const videoStartResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/projects/${projectId}/lessons/${firstLessonId}/video/generations`),
  );
  await page.getByRole("button", { name: "生成 6 秒短片" }).click();
  const videoAccepted = (await (await videoStartResponse).json()) as {
    data: { job_id: string };
  };
  await expect(page.getByRole("progressbar", { name: /短片生成进度/ })).toHaveAttribute(
    "aria-valuenow",
    /^(?:0|[1-9]\d?|100)$/,
  );
  const video = page.getByLabel("6 秒课堂导入短片");
  await expect(video).toBeVisible({ timeout: generationTimeout });

  const generatedVideo = await page.evaluate(
    async ({ baseUrl, lessonId, exactProjectId }) => {
      const response = await fetch(
        `${baseUrl}/projects/${exactProjectId}/lessons/${lessonId}/video`,
        { credentials: "include" },
      );
      return (await response.json()) as {
        data: {
          candidate: {
            adoption_id: string | null;
            file_asset_version_id: string;
            playback_url: string;
            result_id: string;
            saved_binding_id: string | null;
          };
          job: { id: string; status: string };
        };
      };
    },
    { baseUrl: apiBaseUrl, exactProjectId: projectId, lessonId: firstLessonId },
  );
  expect(generatedVideo.data.job.id).toBe(videoAccepted.data.job_id);
  expect(generatedVideo.data.job.status).toBe("succeeded");
  expect(generatedVideo.data.candidate.adoption_id).toBeNull();
  expect(generatedVideo.data.candidate.saved_binding_id).toBeNull();
  const playback = await page.evaluate(
    async ({ baseUrl, path }) => {
      const response = await fetch(new URL(path, baseUrl), { credentials: "include" });
      return {
        byteLength: (await response.arrayBuffer()).byteLength,
        contentType: response.headers.get("content-type"),
        status: response.status,
      };
    },
    { baseUrl: apiBaseUrl, path: generatedVideo.data.candidate.playback_url },
  );
  expect(playback.status).toBe(200);
  expect(playback.contentType).toContain("video/mp4");
  expect(playback.byteLength).toBeGreaterThan(1_000);

  const videoAdoptionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response
        .url()
        .endsWith(
          `/lessons/${firstLessonId}/video/results/${generatedVideo.data.candidate.result_id}/adoptions`,
        ),
  );
  await page.getByRole("button", { name: "采用这段短片" }).click();
  const videoAdoption = (await (await videoAdoptionResponse).json()) as {
    data: { id: string };
  };
  const videoSaveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response
        .url()
        .endsWith(`/lessons/${firstLessonId}/video/adoptions/${videoAdoption.data.id}/save`),
  );
  await page.getByRole("button", { name: "保存到当前课时" }).click();
  expect((await videoSaveResponse).status()).toBe(200);
  await expect(page.getByText("已保存到当前课时")).toBeVisible();

  await page.reload();
  await expect(page.getByText("已保存到当前课时")).toBeVisible();
  const restoredVideo = await page.evaluate(
    async ({ baseUrl, lessonId, exactProjectId }) => {
      const response = await fetch(
        `${baseUrl}/projects/${exactProjectId}/lessons/${lessonId}/video`,
        { credentials: "include" },
      );
      return (await response.json()) as {
        data: {
          candidate: {
            adoption_id: string;
            file_asset_version_id: string;
            result_id: string;
            saved_binding_id: string;
          };
          job: { id: string; status: string };
        };
      };
    },
    { baseUrl: apiBaseUrl, exactProjectId: projectId, lessonId: firstLessonId },
  );
  expect(restoredVideo.data.job).toEqual(generatedVideo.data.job);
  expect(restoredVideo.data.candidate.result_id).toBe(generatedVideo.data.candidate.result_id);
  expect(restoredVideo.data.candidate.file_asset_version_id).toBe(
    generatedVideo.data.candidate.file_asset_version_id,
  );
  expect(restoredVideo.data.candidate.adoption_id).toBe(videoAdoption.data.id);
  expect(restoredVideo.data.candidate.saved_binding_id).toBeTruthy();

  await page.getByRole("link", { name: "返回项目" }).click();
  const secondLesson = page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name: "第二课时隔离验证" }) });
  await secondLesson.getByRole("link", { name: "查看教案" }).click();
  const secondLessonId = /\/lessons\/([0-9a-f-]+)\/work/.exec(page.url())?.[1];
  if (!secondLessonId) throw new Error("Second lesson workbench URL is missing its exact ID");
  expect(secondLessonId).toBeTruthy();
  expect(secondLessonId).not.toBe(firstLessonId);
  await expect(page.getByText("当前课时还没有教案正文。")).toBeVisible();
  await expect(page.getByRole("progressbar")).toHaveCount(0);

  const secondStartedResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v2\/node-runs\/[0-9a-f-]+\/start$/.test(response.url()),
  );
  await page.getByRole("button", { name: "生成十二部分教案" }).click();
  const secondAccepted = (await (await secondStartedResponse).json()) as {
    data: { job_id: string };
  };
  await expectGenerationProgress(page);
  await expect(page.getByText("Lesson-plan generation completed")).toBeVisible({
    timeout: generationTimeout,
  });
  await expect(page.getByLabel(/^一、教学内容 课题 \d+$/)).toBeVisible();

  const secondGeneratedJob = await page.evaluate(
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
    { baseUrl: apiBaseUrl, jobId: secondAccepted.data.job_id },
  );
  expect(secondGeneratedJob.data.status).toBe("succeeded");
  expect(secondGeneratedJob.data.lesson_unit_id).toBe(secondLessonId);
  expect(secondGeneratedJob.data.result_artifact_version_id).toBeTruthy();
  expect(secondGeneratedJob.data.result_artifact_version_id).not.toBe(
    generatedJob.data.result_artifact_version_id,
  );

  const secondFacts = await page.evaluate(
    async ({ baseUrl, lessonId, projectId: exactProjectId }) => {
      const [artifactResponse, jobsResponse, introArtifactResponse, introJobsResponse] =
        await Promise.all([
          fetch(`${baseUrl}/projects/${exactProjectId}/lessons/${lessonId}/lesson-plan/artifact`, {
            credentials: "include",
          }),
          fetch(
            `${baseUrl}/projects/${exactProjectId}/lessons/${lessonId}/lesson-plan/generation-jobs`,
            { credentials: "include" },
          ),
          fetch(
            `${baseUrl}/projects/${exactProjectId}/lessons/${lessonId}/intro-options/artifact`,
            {
              credentials: "include",
            },
          ),
          fetch(
            `${baseUrl}/projects/${exactProjectId}/lessons/${lessonId}/intro-options/generation-jobs`,
            { credentials: "include" },
          ),
        ]);
      return {
        artifact: (await artifactResponse.json()) as {
          data: {
            artifact: {
              current_draft: {
                content: {
                  teaching_content: {
                    lesson_plan_key: string;
                    lesson_topic: string;
                    source_lesson_unit_key: string;
                    teaching_evidence_refs: string[];
                  };
                  teaching_objectives: Array<{
                    objective_evidence_refs: string[];
                  }>;
                };
              } | null;
            } | null;
          };
        },
        introArtifact: (await introArtifactResponse.json()) as { data: { artifact: unknown } },
        introJobs: (await introJobsResponse.json()) as { data: { items: unknown[] } },
        jobs: (await jobsResponse.json()) as { data: { items: unknown[] } },
      };
    },
    { baseUrl: apiBaseUrl, lessonId: secondLessonId, projectId },
  );
  const secondTeaching =
    secondFacts.artifact.data.artifact?.current_draft?.content.teaching_content;
  expect(secondTeaching).toEqual(
    expect.objectContaining({
      lesson_plan_key: "LESSON-PLAN-RESCUE-002",
      lesson_topic: "第二课时隔离验证",
      source_lesson_unit_key: "LESSON-RESCUE-002",
    }),
  );
  const secondLessonEvidenceRefs = ["EV-MAT-05", "EV-MAT-06", "EV-MAT-07", "EV-MAT-08"];
  expect(secondTeaching?.teaching_evidence_refs).toEqual(secondLessonEvidenceRefs);
  const secondObjectives =
    secondFacts.artifact.data.artifact?.current_draft?.content.teaching_objectives;
  expect(secondObjectives).toBeDefined();
  const secondObjectiveEvidenceRefs = (secondObjectives ?? []).flatMap(
    (objective) => objective.objective_evidence_refs,
  );
  expect(secondObjectiveEvidenceRefs.sort()).toEqual(secondLessonEvidenceRefs);
  expect(secondFacts.artifact.data.artifact).not.toBeNull();
  expect(secondFacts.jobs.data.items).toHaveLength(1);
  expect(secondFacts.introArtifact.data.artifact).toBeNull();
  expect(secondFacts.introJobs.data.items).toEqual([]);

  const session = await page.evaluate(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/auth/session`, { credentials: "include" });
    return (await response.json()) as { data: { csrf_token: string } };
  }, apiBaseUrl);
  await page.getByRole("button", { name: "打开个人菜单" }).click();
  await page.getByRole("menuitem", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login$/);
  const rejected = await page.evaluate(
    async ({ baseUrl, csrfToken, lessonId }) => {
      const response = await fetch(`${baseUrl}/lessons/${lessonId}/intro-options/node-runs`, {
        body: JSON.stringify({
          generation_mode: "default_nine",
          source_artifact_version_id: null,
        }),
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": "r1-intro-logout-write",
          "X-CSRF-Token": csrfToken,
        },
        method: "POST",
      });
      return response.status;
    },
    { baseUrl: apiBaseUrl, csrfToken: session.data.csrf_token, lessonId: firstLessonId },
  );
  expect(rejected).toBe(401);
});
