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
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/projects$/);
}

test("teacher_reparses_the_exact_failed_material_with_real_api", async ({ page }) => {
  test.setTimeout(180_000);
  await login(page);
  await page.getByRole("link", { name: "继续制作教材重新解析验收" }).click();
  await page.getByRole("link", { name: "教材与解析" }).click();
  await page.getByRole("link", { name: "shanhai-r1-reparse-textbook.pdf" }).click();

  await expect(page.getByText("第 1 次解析")).toBeVisible();
  await expect(page.getByRole("alert", { name: "" })).toContainText("本次解析没有完成");
  const acceptedResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      /\/api\/v2\/projects\/[0-9a-f-]+\/materials\/[0-9a-f-]+\/parse-versions$/.test(
        response.url(),
      ),
  );
  await page.getByRole("button", { name: "重新解析" }).click();
  const accepted = (await (await acceptedResponse).json()) as { data: { job_id: string } };

  await expect(page).toHaveURL(/\/setup\?jobId=[0-9a-f-]+&materialId=[0-9a-f-]+$/);
  await expect(page.getByRole("progressbar", { name: "教材处理进度 100%" })).toBeVisible({
    timeout: 60_000,
  });
  await page.getByRole("link", { name: "查看教材详情" }).click();
  await expect(page.getByText("第 2 次解析")).toBeVisible();
  await expect(page.getByRole("button", { name: "重新解析" })).toHaveCount(0);

  const routeIds = /\/projects\/([0-9a-f-]+)\/materials\/([0-9a-f-]+)/.exec(page.url());
  if (!routeIds?.[1] || !routeIds[2]) throw new Error("Material route IDs are unavailable");
  const facts = await page.evaluate(
    async ({ baseUrl, jobId, materialId, projectId }) => {
      const [jobResponse, parsesResponse] = await Promise.all([
        fetch(`${baseUrl}/generation-jobs/${jobId}`, { credentials: "include" }),
        fetch(`${baseUrl}/projects/${projectId}/materials/${materialId}/parse-versions`, {
          credentials: "include",
        }),
      ]);
      return {
        job: (await jobResponse.json()) as { data: { status: string } },
        parses: (await parsesResponse.json()) as {
          data: {
            items: Array<{
              error_code: string | null;
              file_asset_version_id: string;
              status: string;
              version_no: number;
            }>;
          };
        },
      };
    },
    {
      baseUrl: apiBaseUrl,
      jobId: accepted.data.job_id,
      materialId: routeIds[2],
      projectId: routeIds[1],
    },
  );
  expect(facts.job.data.status).toBe("succeeded");
  expect(facts.parses.data.items).toHaveLength(2);
  expect(facts.parses.data.items[0]).toMatchObject({
    error_code: null,
    status: "succeeded",
    version_no: 2,
  });
  expect(facts.parses.data.items[1]).toMatchObject({
    error_code: "PDF_DAMAGED",
    status: "failed",
    version_no: 1,
  });
  expect(facts.parses.data.items[0]?.file_asset_version_id).toBe(
    facts.parses.data.items[1]?.file_asset_version_id,
  );

  await page.reload();
  await expect(page.getByText("第 2 次解析")).toBeVisible();
  await expect(page.getByRole("button", { name: "重新解析" })).toHaveCount(0);
});
