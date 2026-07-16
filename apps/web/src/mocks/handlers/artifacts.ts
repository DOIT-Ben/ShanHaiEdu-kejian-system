import { http } from "msw";
import { getDb } from "../db";
import { approveArtifact } from "../engine";
import { publishEvent } from "../events";
import type { IntroDesignContent } from "@/entities/content";
import { api, fail, guard, ok, simulateLatency } from "./http";

function findArtifactAnywhere(versionId: string) {
  const db = getDb();
  for (const project of db.projects.values()) {
    if (project.evidence?.artifact_version_id === versionId) {
      return { artifact: project.evidence, project, lessonState: null, node: null };
    }
    for (const version of project.divisionVersions) {
      if (version.artifact_version_id === versionId) {
        return { artifact: version, project, lessonState: null, node: null };
      }
    }
    for (const lessonState of project.lessons) {
      for (const node of lessonState.nodes.values()) {
        const artifact = node.artifactVersions.find((v) => v.artifact_version_id === versionId);
        if (artifact) return { artifact, project, lessonState, node };
      }
    }
  }
  return null;
}

export const artifactHandlers = [
  http.get(api("/artifact-versions/:versionId"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const found = findArtifactAnywhere(String(params.versionId));
    if (!found) return fail(404, "NOT_FOUND", "产物版本不存在。");
    return ok(found.artifact);
  }),

  http.post(api("/artifact-versions/:versionId/approve"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const versionId = String(params.versionId);
    const found = findArtifactAnywhere(versionId);
    if (!found) return fail(404, "NOT_FOUND", "产物版本不存在。");
    const body = (await request.json().catch(() => ({}))) as {
      note?: string;
      override_warning_rule_ids?: string[];
      override_reason?: string;
    };

    // 导入设计：必须先选定一套方案
    if (found.node && found.artifact.artifact_type === "intro_design") {
      const content = found.artifact.content as unknown as IntroDesignContent;
      if (!content.selected_option_id) {
        return fail(422, "SELECTION_REQUIRED", "请先在九套方案中选定一套，再批准该步骤。", { action: "select_option" });
      }
    }
    // 校验错误未处理时禁止批准（警告可说明理由后批准）
    if (found.node) {
      const blockingErrors = found.node.validationResults.filter((v) => v.severity === "error" && !v.passed);
      if (blockingErrors.length > 0) {
        return fail(422, "VALIDATION_BLOCKING", `还有 ${blockingErrors.length} 项校验未通过：${blockingErrors[0].message}`, {
          action: "resolve_validation",
          details: { rule_ids: blockingErrors.map((v) => v.rule_id) },
        });
      }
      const warnings = found.node.validationResults.filter((v) => v.severity === "warning" && !v.passed);
      const overridden = new Set(body.override_warning_rule_ids ?? []);
      const unhandled = warnings.filter((w) => !overridden.has(w.rule_id));
      if (unhandled.length > 0 && !body.override_reason) {
        return fail(422, "WARNINGS_UNCONFIRMED", "存在未确认的校验警告，请确认警告并填写说明后批准。", {
          action: "confirm_warnings",
          details: { rule_ids: unhandled.map((w) => w.rule_id) },
        });
      }
    }

    const approved = approveArtifact(db, versionId, body.note);
    if (!approved) return fail(404, "NOT_FOUND", "产物版本不存在。");
    return ok(approved);
  }),

  http.post(api("/artifact-versions/:versionId/confirm-stale"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const found = findArtifactAnywhere(String(params.versionId));
    if (!found) return fail(404, "NOT_FOUND", "产物版本不存在。");
    if (found.artifact.status !== "stale") {
      return fail(409, "NOT_STALE", "该版本不处于失效状态。");
    }
    found.artifact.status = "approved";
    found.artifact.stale_reason = null;
    if (found.node) {
      found.node.summary.status = "approved";
      publishEvent({
        event_type: "node.status_changed",
        project_id: found.project.project.project_id,
        lesson_id: found.lessonState?.lesson.lesson_id ?? null,
        node_key: found.node.summary.node_key,
        task_id: null,
        payload: { status: "approved" },
      });
    }
    return ok(found.artifact);
  }),
];
