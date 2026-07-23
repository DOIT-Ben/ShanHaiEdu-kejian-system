import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getProjectAutomationPolicyVersioned,
  updateProjectAutomationPolicy,
} from "./automationPolicyApi";

function policyResponse(etag: string) {
  return new Response(
    JSON.stringify({
      data: {
        mode: "guided",
        node_rules: [],
        policy_version: 2,
        project_id: "01960000-0000-7000-8000-000000000001",
        updated_at: "2026-07-20T00:00:00Z",
        workflow_definition_version_id: "01960000-0000-7000-8000-000000000002",
      },
      request_id: "req-policy",
    }),
    { headers: { "Content-Type": "application/json", ETag: etag }, status: 200 },
  );
}

describe("automationPolicyApi", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("读取策略及 ETag", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(policyResponse('"policy-v2"')));

    await expect(
      getProjectAutomationPolicyVersioned("01960000-0000-7000-8000-000000000001"),
    ).resolves.toMatchObject({ etag: '"policy-v2"', policy: { mode: "guided" } });
  });

  it("更新策略时发送 If-Match 和 Idempotency-Key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(policyResponse('"policy-v3"'));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      updateProjectAutomationPolicy({
        etag: '"policy-v2"',
        idempotencyKey: "policy-update-2",
        input: { mode: "guided", node_rules: [{ node_key: "lesson-plan", pause_after: true }] },
        projectId: "01960000-0000-7000-8000-000000000001",
      }),
    ).resolves.toMatchObject({ etag: '"policy-v3"', policy: { policy_version: 2 } });

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.headers.get("If-Match")).toBe('"policy-v2"');
    expect(request.headers.get("Idempotency-Key")).toBe("policy-update-2");
    await expect(request.json()).resolves.toMatchObject({ mode: "guided" });
  });
});
