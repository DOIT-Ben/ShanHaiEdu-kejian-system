import { http } from "msw";
import type { Delivery, DeliveryItem, FileObject } from "@/shared/api/types";
import type { FinalCutContent, AudioSubtitleContent, PptExportContent } from "@/entities/content";
import { getDb, minutesAgo, type ProjectState } from "../db";
import { startTask } from "../engine";
import { makeFileObject } from "../fixtures/files";
import { api, fail, guard, ok, simulateLatency } from "./http";

function fileFromAsset(assetId: string | null | undefined): FileObject | null {
  if (!assetId) return null;
  const record = getDb().assets.get(assetId);
  return record?.versions[0]?.file_object ?? null;
}

/** 依据课时节点状态实时计算交付清单。 */
export function buildDelivery(state: ProjectState, lessonId?: string | null): Delivery {
  const lessons = lessonId ? state.lessons.filter((l) => l.lesson.lesson_id === lessonId) : state.lessons;
  const items: DeliveryItem[] = [];
  const blockers: Delivery["blockers"] = [];
  const outputScope = state.project.output_scope ?? { ppt: true, video: true };

  for (const lessonState of lessons) {
    const lesson = lessonState.lesson;
    const planNode = lessonState.nodes.get("lesson_plan");
    const planApproved = planNode?.summary.status === "approved";
    items.push({
      item_key: `dl_${lesson.lesson_id}_plan`,
      lesson_id: lesson.lesson_id,
      category: "lesson_plan",
      title: `${lesson.title}·教案`,
      status: state.delivery.package_file && planApproved ? "delivered" : planApproved ? "ready" : "pending",
      file_object: null,
      version_number: planNode?.artifactVersions[0]?.version_number ?? null,
      quality_passed: planApproved ? true : null,
      generated_at: planNode?.artifactVersions[0]?.created_at ?? null,
    });
    if (!planApproved) {
      blockers.push({ code: "LESSON_PLAN_NOT_APPROVED", message: `「${lesson.title}」的教案还未批准`, lesson_id: lesson.lesson_id, node_key: "lesson_plan" });
    }

    if (outputScope.ppt) {
      const exportNode = lessonState.nodes.get("ppt_export");
      const exportArtifact = exportNode?.artifactVersions.find((v) => v.status === "approved");
      const exportContent = exportArtifact?.content as PptExportContent | undefined;
      const pptSkipped = exportNode?.summary.status === "skipped";
      const pptFile = exportContent?.file_object_id
        ? (exportArtifact?.file_objects?.[0] ?? { file_object_id: exportContent.file_object_id, file_name: `${lesson.title}.pptx`, mime_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation", size_bytes: 8_400_000, preview_url: null })
        : null;
      if (!pptSkipped) {
        items.push({
          item_key: `dl_${lesson.lesson_id}_ppt`,
          lesson_id: lesson.lesson_id,
          category: "ppt",
          title: `${lesson.title}·教学PPT`,
          status: state.delivery.package_file && pptFile ? "delivered" : pptFile ? "ready" : planApproved ? "pending" : "blocked",
          file_object: pptFile,
          version_number: exportArtifact?.version_number ?? null,
          quality_passed: pptFile ? true : null,
          generated_at: exportArtifact?.created_at ?? null,
        });
        if (!pptFile) {
          blockers.push({ code: "PPT_NOT_EXPORTED", message: `「${lesson.title}」的 PPT 还未完成导出`, lesson_id: lesson.lesson_id, node_key: "ppt_export" });
        }
      }
    }

    if (outputScope.video) {
      const finalNode = lessonState.nodes.get("video_final_cut");
      const videoSkipped = finalNode?.summary.status === "skipped";
      const finalArtifact = finalNode?.artifactVersions.find((v) => v.status === "approved");
      const finalContent = finalArtifact?.content as FinalCutContent | undefined;
      const videoFile = fileFromAsset(finalContent?.video_asset_id);
      if (!videoSkipped) {
        items.push({
          item_key: `dl_${lesson.lesson_id}_video`,
          lesson_id: lesson.lesson_id,
          category: "video",
          title: `${lesson.title}·导入视频`,
          status: state.delivery.package_file && videoFile ? "delivered" : videoFile ? "ready" : "blocked",
          file_object: videoFile,
          version_number: finalArtifact?.version_number ?? null,
          quality_passed: videoFile ? true : null,
          generated_at: finalArtifact?.created_at ?? null,
        });
        if (!videoFile) {
          blockers.push({ code: "VIDEO_NOT_READY", message: `「${lesson.title}」缺少批准的视频成片`, lesson_id: lesson.lesson_id, node_key: "video_final_cut" });
        }
        const audioNode = lessonState.nodes.get("video_audio_subtitle");
        const audioArtifact = audioNode?.artifactVersions.find((v) => v.status === "approved");
        const audioContent = audioArtifact?.content as AudioSubtitleContent | undefined;
        const subtitleFile = fileFromAsset(audioContent?.subtitle_asset_id);
        if (subtitleFile) {
          items.push({
            item_key: `dl_${lesson.lesson_id}_subtitle`,
            lesson_id: lesson.lesson_id,
            category: "subtitle",
            title: `${lesson.title}·字幕文件`,
            status: state.delivery.package_file ? "delivered" : "ready",
            file_object: subtitleFile,
            version_number: audioArtifact?.version_number ?? null,
            quality_passed: true,
            generated_at: audioArtifact?.created_at ?? null,
          });
        }
      }
    }
  }

  items.push({
    item_key: "dl_quality_report",
    lesson_id: null,
    category: "quality_report",
    title: "质量检查报告",
    status: state.delivery.package_file ? "delivered" : blockers.length === 0 && items.length > 0 ? "ready" : "pending",
    file_object: null,
    version_number: null,
    quality_passed: blockers.length === 0 ? true : null,
    generated_at: null,
  });
  if (state.delivery.package_file) {
    items.push({
      item_key: "dl_package",
      lesson_id: null,
      category: "package",
      title: "交付包（ZIP）",
      status: "delivered",
      file_object: state.delivery.package_file,
      version_number: null,
      quality_passed: true,
      generated_at: state.delivery.packaged_at,
    });
  }

  const packagingTask = state.delivery.package_task_id ? getDb().tasks.get(state.delivery.package_task_id) : null;
  const packaging = packagingTask && (packagingTask.status === "queued" || packagingTask.status === "running" || packagingTask.status === "waiting_provider" || packagingTask.status === "downloading");
  return {
    status: state.delivery.package_file ? "completed" : packaging ? "packaging" : blockers.length === 0 && lessons.length > 0 ? "ready" : "not_ready",
    items,
    blockers,
    package_task_id: state.delivery.package_task_id,
    packaged_at: state.delivery.packaged_at,
    package_file: state.delivery.package_file,
  };
}

export const deliveryHandlers = [
  http.get(api("/projects/:projectId/delivery"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const state = getDb().projects.get(String(params.projectId));
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    const lessonId = new URL(request.url).searchParams.get("lesson_id");
    return ok(buildDelivery(state, lessonId));
  }),

  http.post(api("/projects/:projectId/delivery/package-runs"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const projectId = String(params.projectId);
    const state = db.projects.get(projectId);
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    const idempotencyKey = request.headers.get("idempotency-key");
    if (!idempotencyKey || idempotencyKey.length < 16) {
      return fail(400, "IDEMPOTENCY_KEY_REQUIRED", "缺少幂等键，请刷新后重试。");
    }
    const idemKey = `package:${projectId}:${idempotencyKey}`;
    if (db.idempotency.has(idemKey)) {
      const existing = db.tasks.get(db.idempotency.get(idemKey)!);
      if (existing) return ok(existing, { status: 202 });
    }
    const current = buildDelivery(state);
    if (current.blockers.length > 0) {
      return fail(409, "DELIVERY_BLOCKED", "还有未完成的交付项，暂时不能打包。", {
        action: "resolve_blockers",
        details: { blockers: current.blockers },
      });
    }
    const task = startTask({
      taskType: "delivery_package",
      projectId,
      durationMs: 9000,
      providerName: "平台打包服务",
      onComplete: (mockDb) => {
        const projectState = mockDb.projects.get(projectId);
        if (!projectState) return;
        projectState.delivery.package_file = makeFileObject({
          fileName: `${projectState.project.name}_交付包.zip`,
          mimeType: "application/zip",
          sizeBytes: 96_000_000,
        });
        projectState.delivery.packaged_at = minutesAgo(0);
        projectState.delivery.status = "completed";
      },
    });
    state.delivery.package_task_id = task.task_id;
    db.idempotency.set(idemKey, task.task_id);
    return ok(task, { status: 202 });
  }),
];
