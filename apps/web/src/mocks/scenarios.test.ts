import { describe, expect, it, beforeEach } from "vitest";
import { client, unwrap, setCsrfToken, AppError } from "@/shared/api";
import { seedDb } from "@/mocks/seed";
import { getDb } from "@/mocks/db";

/**
 * MSW 场景测试：直接经由真实 API 客户端打 Mock Handler，
 * 验证 Envelope、鉴权、场景行为开关与错误分支。
 */

async function login(): Promise<void> {
  const result = await client.POST("/auth/login", {
    body: { identifier: "teacher@shanhai.edu", password: "demo1234" },
  });
  const { data } = unwrap(result);
  setCsrfToken(data.csrf_token);
}

describe("场景：auth.login.success", () => {
  it("登录成功返回用户与 CSRF Token", async () => {
    const result = await client.POST("/auth/login", {
      body: { identifier: "teacher@shanhai.edu", password: "demo1234" },
    });
    const { data } = unwrap(result);
    expect(data.user.role).toBe("teacher");
    expect(data.csrf_token).toMatch(/^csrf-/);
  });
});

describe("场景：auth.login.failure", () => {
  beforeEach(() => {
    seedDb("auth.login.failure");
  });
  it("登录失败返回 401 错误 Envelope", async () => {
    const result = await client.POST("/auth/login", {
      body: { identifier: "teacher@shanhai.edu", password: "wrong" },
    });
    expect(() => unwrap(result)).toThrowError(AppError);
    try {
      unwrap(result);
    } catch (error) {
      expect((error as AppError).code).toBe("INVALID_CREDENTIALS");
      expect((error as AppError).status).toBe(401);
    }
  });
});

describe("场景：projects.multiple（默认）", () => {
  it("登录后可拉取项目列表", async () => {
    await login();
    const result = await client.GET("/projects", {});
    const { data } = unwrap(result);
    expect(data.length).toBeGreaterThan(1);
    expect(data[0].project_id).toBeTruthy();
    expect(data[0].row_version).toBeGreaterThanOrEqual(1);
  });

  it("未登录访问项目返回 401", async () => {
    const result = await client.GET("/projects", {});
    try {
      unwrap(result);
      expect.unreachable("应当抛出 401");
    } catch (error) {
      expect((error as AppError).status).toBe(401);
    }
  });
});

describe("场景：projects.empty", () => {
  beforeEach(() => {
    seedDb("projects.empty");
  });
  it("返回空项目列表（空状态用例）", async () => {
    await login();
    const result = await client.GET("/projects", {});
    const { data } = unwrap(result);
    expect(data).toHaveLength(0);
  });
});

describe("场景：lesson_division.conflict", () => {
  beforeEach(() => {
    seedDb("lesson_division.conflict");
  });
  it("保存课时划分返回 409 与 server_row_version", async () => {
    await login();
    const db = getDb();
    const projectId = [...db.projects.keys()][0];
    const result = await client.PATCH("/projects/{projectId}/lesson-divisions/current", {
      params: { path: { projectId } },
      body: { content: { lessons: [] }, row_version: 1 },
    });
    try {
      unwrap(result);
      expect.unreachable("应当抛出 409");
    } catch (error) {
      const appError = error as AppError;
      expect(appError.status).toBe(409);
      expect(appError.code).toBe("VERSION_CONFLICT");
      expect((appError.details as { server_row_version?: number }).server_row_version).toBeGreaterThan(1);
    }
  });
});

describe("场景：budget.authorization_required", () => {
  beforeEach(() => {
    seedDb("budget.authorization_required");
  });
  it("费用预估提示需要预算授权，并可创建授权", async () => {
    await login();
    const db = getDb();
    const projectEntry = [...db.projects.values()][0];
    const lessonState = projectEntry.lessons[0];
    const lessonId = lessonState.lesson.lesson_id;
    const promptVersionId =
      lessonState.nodes.get("video_clips")?.promptVersions[0]?.prompt_version_id ?? "pv_placeholder";
    const estimateResult = await client.POST("/lessons/{lessonId}/nodes/{nodeKey}/cost-estimate", {
      params: { path: { lessonId, nodeKey: "video_clips" } },
      body: { prompt_version_id: promptVersionId, model_profile: "recommended", parameters: {} },
    });
    const { data: estimate } = unwrap(estimateResult);
    expect(estimate.requires_authorization).toBe(true);
    expect(estimate.maximum_minor_units).toBeGreaterThan(0);

    const authResult = await client.POST("/lessons/{lessonId}/nodes/{nodeKey}/budget-authorizations", {
      params: { path: { lessonId, nodeKey: "video_clips" } },
      body: { estimated_max_minor_units: estimate.maximum_minor_units, reason: "教学需要，确认继续" },
    });
    const { data: authorization } = unwrap(authResult);
    expect(authorization.budget_authorization_id).toBeTruthy();
  });
});
