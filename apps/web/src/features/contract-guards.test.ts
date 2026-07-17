import { describe, expect, it } from "vitest";
import { client, unwrap } from "@/shared/api/client";
import { AppError } from "@/shared/api/AppError";
import { db } from "@/mocks/db";
import { ID } from "@/mocks/ids";

/**
 * 走真实 mock 世界的合同集成测试：
 * 幂等、乐观锁（428/409）、审批链、密钥只写。
 */

async function loginTeacher() {
  unwrap(
    await client.POST("/auth/login", {
      body: { email: "teacher@shanhai.edu", password: "demo1234" },
    }),
  );
}

async function loginAdmin() {
  unwrap(
    await client.POST("/auth/login", {
      body: { email: "admin@shanhai.edu", password: "demo1234" },
    }),
  );
}

describe("合同保护：乐观锁与幂等", () => {
  it("缺少 If-Match 返回 428 PRECONDITION_REQUIRED", async () => {
    await loginTeacher();
    const lessonId = ID.lessonA2;
    const options = unwrap(
      await client.GET("/lessons/{lesson_id}/intro-options", {
        params: { path: { lesson_id: lessonId } },
      }),
    );
    const optionKey = options.data.options[0]!.option_key;
    const result = await client.PATCH("/lessons/{lesson_id}/intro-options/{option_key}", {
      params: {
        path: { lesson_id: lessonId, option_key: optionKey },
        header: { "If-Match": "" },
      },
      body: { title: "新标题" },
    });
    expect(() => unwrap(result as never)).toThrowError(AppError);
    try {
      unwrap(result as never);
    } catch (error) {
      expect((error as AppError).status).toBe(428);
      expect((error as AppError).code).toBe("PRECONDITION_REQUIRED");
    }
  });

  it("旧 ETag 返回 409 EDIT_CONFLICT，并附 current_etag", async () => {
    await loginTeacher();
    const lessonId = ID.lessonA2;
    const options = unwrap(
      await client.GET("/lessons/{lesson_id}/intro-options", {
        params: { path: { lesson_id: lessonId } },
      }),
    );
    const optionKey = options.data.options[0]!.option_key;
    const etag = options.etag!;
    // 第一次修改成功，方案集版本 +1
    unwrap(
      await client.PATCH("/lessons/{lesson_id}/intro-options/{option_key}", {
        params: { path: { lesson_id: lessonId, option_key: optionKey }, header: { "If-Match": etag } },
        body: { title: "第一次修改" },
      }),
    );
    // 拿旧 etag 再改 → 409
    const stale = await client.PATCH("/lessons/{lesson_id}/intro-options/{option_key}", {
      params: { path: { lesson_id: lessonId, option_key: optionKey }, header: { "If-Match": etag } },
      body: { title: "第二次修改" },
    });
    try {
      unwrap(stale as never);
      expect.unreachable("应当抛出 409");
    } catch (error) {
      const appError = error as AppError;
      expect(appError.status).toBe(409);
      expect(appError.code).toBe("EDIT_CONFLICT");
      expect(appError.isEditConflict).toBe(true);
      expect((appError.details as { current_etag?: string }).current_etag).toBeTruthy();
    }
  });

  it("同一 Idempotency-Key 重复启动返回同一任务", async () => {
    await loginTeacher();
    const runs = unwrap(
      await client.GET("/lessons/{lesson_id}/node-runs", {
        params: { path: { lesson_id: ID.lessonA3 } },
      }),
    );
    const planRun = runs.data.items.find((r) => r.node_key === "lesson_plan")!;
    expect(planRun.status).toBe("ready");
    const key = "test-idem-0001";
    const first = unwrap(
      await client.POST("/node-runs/{node_run_id}/start", {
        params: { path: { node_run_id: planRun.id }, header: { "Idempotency-Key": key } },
        body: {},
      }),
    );
    const second = unwrap(
      await client.POST("/node-runs/{node_run_id}/start", {
        params: { path: { node_run_id: planRun.id }, header: { "Idempotency-Key": key } },
        body: {},
      }),
    );
    expect(second.data.job_id).toBe(first.data.job_id);
  });
});

describe("审批链：带警告的教案确认", () => {
  it("未确认警告 → 409 WARNINGS_UNACKNOWLEDGED；确认后批准成功", async () => {
    await loginTeacher();
    const versionId = ID.avLessonPlanA2;
    const blind = await client.POST("/artifact-versions/{artifact_version_id}/approve", {
      params: { path: { artifact_version_id: versionId }, header: { "Idempotency-Key": "approve-1" } },
      body: {},
    });
    try {
      unwrap(blind as never);
      expect.unreachable("应当要求先确认警告");
    } catch (error) {
      const appError = error as AppError;
      expect(appError.status).toBe(409);
      expect(appError.code).toBe("WARNINGS_UNACKNOWLEDGED");
      const warnings = (appError.details as { warnings?: { key: string }[] }).warnings ?? [];
      expect(warnings.length).toBeGreaterThan(0);

      const approved = unwrap(
        await client.POST("/artifact-versions/{artifact_version_id}/approve", {
          params: { path: { artifact_version_id: versionId }, header: { "Idempotency-Key": "approve-2" } },
          body: {
            acknowledged_warning_keys: warnings.map((w) => w.key),
            acknowledgement_note: "教师已确认，弹性处理。",
          },
        }),
      );
      expect(approved.data.review_status).toBe("approved");
    }
  });
});

describe("模型密钥只写（安全红线）", () => {
  it("PATCH 提交明文密钥后，任何响应只含状态与尾号", async () => {
    await loginAdmin();
    const providers = unwrap(await client.GET("/admin/providers"));
    const target = providers.data.items[0]!;
    const secret = "unit-test-secret-abcd1234";
    const updated = unwrap(
      await client.PATCH("/admin/providers/{provider_id}", {
        params: {
          path: { provider_id: target.id },
          header: { "If-Match": "*", "Idempotency-Key": "prov-00000001" },
        },
        body: { secret },
      }),
    );
    const body = JSON.stringify(updated.data);
    expect(body).not.toContain(secret);
    expect(updated.data.secret_status).toBe("configured");
    expect(updated.data.secret_tail).toBe(secret.slice(-4));
    // 列表同样不回显
    const again = unwrap(await client.GET("/admin/providers"));
    expect(JSON.stringify(again.data)).not.toContain(secret);
  });

  it("教师访问管理端接口返回 403 FORBIDDEN", async () => {
    await loginTeacher();
    const denied = await client.GET("/admin/providers");
    try {
      unwrap(denied as never);
      expect.unreachable("教师不应有权限");
    } catch (error) {
      expect((error as AppError).status).toBe(403);
      expect((error as AppError).code).toBe("FORBIDDEN");
    }
  });
});

describe("三类九套选择", () => {
  it("确认方案后视频分支基于所选快照", async () => {
    await loginTeacher();
    const lessonId = ID.lessonA2;
    const options = unwrap(
      await client.GET("/lessons/{lesson_id}/intro-options", {
        params: { path: { lesson_id: lessonId } },
      }),
    );
    const pick = options.data.options.find((o) => o.category === "science")!;
    const selected = unwrap(
      await client.POST("/lessons/{lesson_id}/intro-selections", {
        params: { path: { lesson_id: lessonId }, header: { "Idempotency-Key": "sel-00000001" } },
        body: {
          intro_option_set_version_id: options.data.option_set_id,
          option_key: pick.option_key,
        },
      }),
    );
    expect(selected.data.option_key).toBe(pick.option_key);
    // 选择行为在 mock 世界里同步了课时状态
    expect(db.introSelections.get(lessonId)?.option_key).toBe(pick.option_key);
  });
});
