import { expect, test, type Page, type Response } from "@playwright/test";

type ExpectedResponse = {
  method: string;
  path: RegExp;
  status: number;
};

function requiredEnvironment(name: string) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const accessCode = requiredEnvironment("SHANHAI_E2E_ACCESS_CODE");
const apiBaseUrl = process.env.SHANHAI_E2E_API_BASE_URL ?? "http://127.0.0.1:58080/api/v2";

test.setTimeout(300_000);

test("teacher_completes_textbook_to_intro_and_recovers_after_reload", async ({ page }) => {
  await login(page);
  await page.goto("/app/projects/new");
  await page.getByLabel("项目名称").fill("认识1到5真实教师纵向链");
  await page.getByRole("textbox", { exact: true, name: "知识点" }).fill("1到5的认识");
  await page.locator('input[type="file"]').setInputFiles({
    buffer: twoPagePdfBuffer(),
    mimeType: "application/pdf",
    name: "numbers-one-to-five.pdf",
  });

  await observeResponses(
    page,
    () => page.getByRole("button", { name: "创建项目并上传教材" }).click(),
    [
      { method: "POST", path: /^\/api\/v2\/projects$/, status: 201 },
      {
        method: "POST",
        path: /^\/api\/v2\/projects\/[0-9a-f-]+\/materials\/uploads$/,
        status: 201,
      },
      { method: "PUT", path: /^\/shanhaiedu-ci\/.+/, status: 200 },
      {
        method: "POST",
        path: /^\/api\/v2\/projects\/[0-9a-f-]+\/materials\/[0-9a-f-]+\/confirm$/,
        status: 202,
      },
      {
        method: "GET",
        path: /^\/api\/v2\/generation-jobs\/[0-9a-f-]+\/events\/stream$/,
        status: 200,
      },
    ],
  );
  await expect(page).toHaveURL(/\/app\/projects\/[0-9a-f-]+\/setup\?/);
  const projectId = requiredUrlCapture(page.url(), /\/app\/projects\/([0-9a-f-]+)\/setup/);
  await expect(page.getByRole("heading", { name: "教材已经准备好" })).toBeVisible({
    timeout: 90_000,
  });

  await observeResponses(page, () => page.getByRole("link", { name: "查看教材详情" }).click(), [
    {
      method: "GET",
      path: /^\/api\/v2\/projects\/[0-9a-f-]+\/materials\/[0-9a-f-]+\/parse-versions$/,
      status: 200,
    },
  ]);
  await expect(page.getByRole("heading", { name: "教材范围与课时划分" })).toBeVisible();
  await expect(page.getByLabel("起始物理页")).toHaveValue("1");
  await expect(page.getByLabel("结束物理页")).toHaveValue("2");

  await observeResponses(page, () => page.getByRole("button", { name: "提交教材范围" }).click(), [
    {
      method: "POST",
      path: /^\/api\/v2\/projects\/[0-9a-f-]+\/material-scope\/versions$/,
      status: 201,
    },
  ]);
  await expect(page.getByText("教材范围待批准：第 1-2 页")).toBeVisible();
  await observeResponses(page, () => page.getByRole("button", { name: "批准教材范围" }).click(), [
    approvalResponse(),
  ]);
  await expect(page.getByText("已批准教材范围：第 1-2 页")).toBeVisible();

  await observeResponses(
    page,
    () => page.getByRole("button", { name: "生成课时划分" }).click(),
    nodeGenerationResponses("lesson-division"),
  );
  await expect(page.getByRole("heading", { name: "任务已经完成" })).toBeVisible({
    timeout: 90_000,
  });
  await expect(page.getByRole("heading", { name: "审阅课时划分" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText(/第 1 课时 ·/)).toBeVisible();
  await expect(page.getByText(/第 2 课时 ·/)).toBeVisible();
  await validateAndApprove(
    page,
    "运行课时划分质量校验",
    "课时划分质量校验已通过，可以批准当前版本。",
    "批准课时划分",
  );
  await expect(page.getByText("课时划分已批准，正式 LessonUnit 已建立。")).toBeVisible();

  await observeResponses(page, () => page.getByRole("link", { name: "返回项目" }).click(), [
    {
      method: "GET",
      path: new RegExp(`^/api/v2/projects/${projectId}/lessons$`),
      status: 200,
    },
  ]);
  const lessonPlanLinks = page.getByRole("link", { name: "查看教案" });
  await expect(lessonPlanLinks).toHaveCount(2);
  const lessonPlanHrefs = await lessonPlanLinks.evaluateAll((links) =>
    links.map((link) => (link as HTMLAnchorElement).href),
  );

  for (const href of lessonPlanHrefs) {
    await generateAndApproveLessonPlan(page, href);
  }

  const firstLessonPlanHref = lessonPlanHrefs[0];
  if (!firstLessonPlanHref) throw new Error("the first lesson plan route is missing");
  const introHref = firstLessonPlanHref.replace(/\/lesson_plan$/, "/intro_options");
  await page.goto(introHref);
  await expect(page.getByRole("heading", { name: "三类九套课堂导入" })).toBeVisible();
  await observeResponses(
    page,
    () => page.getByRole("button", { name: "生成三类九套" }).click(),
    nodeGenerationResponses("intro-options"),
  );
  await expect(page.getByRole("heading", { name: "任务已经完成" })).toBeVisible({
    timeout: 90_000,
  });
  await expect(page.getByRole("heading", { name: "待确认三类九套" })).toBeVisible({
    timeout: 30_000,
  });
  await validateAndApprove(
    page,
    "运行导入方案质量校验",
    "导入方案质量校验已通过，可以批准当前版本。",
    "批准三类九套",
  );

  const selectableOptions = page.getByRole("button", { name: /^选用方案：/ });
  await expect(selectableOptions).toHaveCount(9);
  await observeResponses(page, () => selectableOptions.first().click(), [
    {
      method: "POST",
      path: /^\/api\/v2\/lessons\/[0-9a-f-]+\/intro-selections$/,
      status: 201,
    },
  ]);
  const selectionStatus = page.getByRole("status").filter({ hasText: "当前选择：" });
  await expect(selectionStatus).toBeVisible();
  const selectedText = await selectionStatus.textContent();
  const sessionId = await currentSessionId(page);

  await page.reload();
  await expect(page.getByRole("heading", { name: "三类九套课堂导入" })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "当前选择：" })).toHaveText(
    selectedText ?? "",
  );
  await expect(page.getByRole("button", { name: /^(已选方案|选用方案)：/ })).toHaveCount(9);
  expect(await currentSessionId(page)).toBe(sessionId);
});

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("学校访问码").fill(accessCode);
  await observeResponses(page, () => page.getByRole("button", { name: "登录" }).click(), [
    { method: "POST", path: /^\/api\/v2\/auth\/session$/, status: 201 },
  ]);
  await expect(page).toHaveURL(/\/app\/projects$/);
}

async function generateAndApproveLessonPlan(page: Page, href: string) {
  await page.goto(href);
  await expect(page.getByRole("heading", { name: "十二部分教案生成" })).toBeVisible();
  await observeResponses(
    page,
    () => page.getByRole("button", { name: "生成十二部分教案" }).click(),
    nodeGenerationResponses("lesson-plan"),
  );
  await expect(page.getByRole("heading", { name: "任务已经完成" })).toBeVisible({
    timeout: 90_000,
  });
  await expect(page.getByRole("button", { name: "运行教案质量校验" })).toBeVisible({
    timeout: 30_000,
  });
  await validateAndApprove(
    page,
    "运行教案质量校验",
    "教案质量校验已通过，可以批准当前版本。",
    "批准当前版本",
  );
  await expect(page.getByText(/已批准版本/).last()).toBeVisible();
}

async function validateAndApprove(
  page: Page,
  qualityButton: string,
  passedMessage: string,
  approvalButton: string,
) {
  await observeResponses(page, () => page.getByRole("button", { name: qualityButton }).click(), [
    {
      method: "POST",
      path: /^\/api\/v2\/artifact-versions\/[0-9a-f-]+\/quality-validations$/,
      status: 202,
    },
  ]);
  await expect(page.getByText(passedMessage)).toBeVisible({ timeout: 60_000 });
  await observeResponses(page, () => page.getByRole("button", { name: approvalButton }).click(), [
    approvalResponse(),
  ]);
}

function approvalResponse(): ExpectedResponse {
  return {
    method: "POST",
    path: /^\/api\/v2\/artifact-versions\/[0-9a-f-]+\/approvals$/,
    status: 201,
  };
}

function nodeGenerationResponses(kind: "intro-options" | "lesson-division" | "lesson-plan") {
  const preparePath =
    kind === "lesson-division"
      ? /^\/api\/v2\/projects\/[0-9a-f-]+\/lesson-division\/node-runs$/
      : kind === "lesson-plan"
        ? /^\/api\/v2\/lessons\/[0-9a-f-]+\/lesson-plan\/node-runs$/
        : /^\/api\/v2\/lessons\/[0-9a-f-]+\/intro-options\/node-runs$/;
  return [
    { method: "POST", path: preparePath, status: 200 },
    { method: "POST", path: /^\/api\/v2\/node-runs\/[0-9a-f-]+\/start$/, status: 202 },
    {
      method: "GET",
      path: /^\/api\/v2\/generation-jobs\/[0-9a-f-]+\/events\/stream$/,
      status: 200,
    },
  ];
}

async function observeResponses(
  page: Page,
  action: () => Promise<void>,
  expected: ExpectedResponse[],
) {
  const pending = expected.map(({ method, path }) =>
    page.waitForResponse(
      (response) =>
        response.request().method() === method && path.test(new URL(response.url()).pathname),
      { timeout: 60_000 },
    ),
  );
  await action();
  const observed = await Promise.all(pending);
  observed.forEach((response, index) => {
    expect(response.status(), responseSummary(response)).toBe(expected[index]?.status);
  });
  return observed;
}

function responseSummary(response: Response) {
  return `${response.request().method()} ${new URL(response.url()).pathname}`;
}

async function currentSessionId(page: Page) {
  return page.evaluate(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/auth/session`, { credentials: "include" });
    if (!response.ok) throw new Error(`session recovery failed with ${String(response.status)}`);
    const body = (await response.json()) as { data: { session_id: string } };
    return body.data.session_id;
  }, apiBaseUrl);
}

function requiredUrlCapture(value: string, pattern: RegExp) {
  const match = value.match(pattern);
  if (!match?.[1]) throw new Error(`URL does not match the R1 route: ${value}`);
  return match[1];
}

function twoPagePdfBuffer() {
  const streams = [
    "BT /F1 18 Tf 72 720 Td (Count objects from one to five.) Tj ET",
    "BT /F1 18 Tf 72 720 Td (Match quantities to numerals from one to five.) Tj ET",
  ] as const;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>",
    `<< /Length ${String(Buffer.byteLength(streams[0], "ascii"))} >>\nstream\n${streams[0]}\nendstream`,
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>",
    `<< /Length ${String(Buffer.byteLength(streams[1], "ascii"))} >>\nstream\n${streams[1]}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let document = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(Buffer.byteLength(document, "ascii"));
    document += `${String(index + 1)} 0 obj\n${object}\nendobj\n`;
  });
  const xrefOffset = Buffer.byteLength(document, "ascii");
  document += `xref\n0 ${String(objects.length + 1)}\n0000000000 65535 f \n`;
  document += offsets
    .slice(1)
    .map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`)
    .join("");
  document += `trailer\n<< /Size ${String(objects.length + 1)} /Root 1 0 R >>\nstartxref\n${String(xrefOffset)}\n%%EOF\n`;
  return Buffer.from(document, "ascii");
}
