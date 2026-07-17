import { http } from "msw";
import { db, emitEvent } from "../db";
import { API, checkIfMatch, fail, idempotent, notFound, ok, requireSession, simulateLatency } from "../http";
import { startJob, produceResults } from "../engine";
import { checkAssetUsageConsistency, type VideoShot } from "@/entities/content/videoShot";

function shotPayload(shot: NonNullable<ReturnType<typeof db.shots.get>>) {
  return {
    id: shot.id,
    shot_key: shot.shot_key,
    position: shot.position,
    status: shot.status,
    shot: shot.shot,
    candidate_count: [...db.results.values()].filter(
      (r) => r.item_key === shot.shot_key && r.node_run_id != null,
    ).length,
    current_clip: shot.current_clip,
    active_job_id: shot.active_job_id,
    failure_reason: shot.failure_reason,
  };
}

/** 视频：项目状态（快照/风格合同）、细分镜、单镜头生成。 */
export const videoHandlers = [
  http.get(API("/lessons/:lessonId/video-project"), async ({ params }) => {
    await simulateLatency(110);
    const denied = requireSession();
    if (denied) return denied;
    const lessonId = params.lessonId as string;
    if (!db.lessons.get(lessonId)) return notFound("课时");
    const project = [...db.videoProjects.values()].find((vp) => vp.lesson_id === lessonId);
    if (!project) return ok(null);
    return ok({
      id: project.id,
      lesson_id: project.lesson_id,
      status: project.status,
      intro_snapshot: project.intro_snapshot,
      style_contract: project.style_contract,
      target_duration_seconds: project.target_duration_seconds,
      created_at: project.created_at,
    });
  }),

  http.get(API("/video-projects/:videoProjectId/shots"), async ({ params }) => {
    await simulateLatency(120);
    const denied = requireSession();
    if (denied) return denied;
    const videoProjectId = params.videoProjectId as string;
    if (!db.videoProjects.get(videoProjectId)) return notFound("视频项目");
    const items = [...db.shots.values()]
      .filter((shot) => shot.video_project_id === videoProjectId)
      .sort((a, b) => a.position - b.position)
      .map(shotPayload);
    return ok({ items });
  }),

  http.put(API("/video-shots/:shotId"), async ({ params, request }) => {
    await simulateLatency(150);
    const denied = requireSession();
    if (denied) return denied;
    const shot = db.shots.get(params.shotId as string);
    if (!shot) return notFound("镜头");
    const conflict = checkIfMatch(request, shot.etag);
    if (conflict) return conflict;
    const body = (await request.json()) as { shot?: VideoShot };
    if (!body.shot) return fail(422, "VALIDATION_FAILED", "缺少镜头内容。");
    const problems = checkAssetUsageConsistency(body.shot);
    if (problems.length > 0) {
      return fail(422, "SHOT_CONTRACT_VIOLATION", problems[0], {
        details: { problems },
      });
    }
    shot.shot = body.shot;
    shot.etag += 1;
    if (shot.status === "adopted") shot.status = "review_required";
    const vp = db.videoProjects.get(shot.video_project_id);
    emitEvent({
      event_type: "video_shot.updated",
      project_id: vp ? db.lessons.get(vp.lesson_id)?.project_id ?? null : null,
      resource: { type: "video_shot", id: shot.id },
    });
    return ok(shotPayload(shot), { etag: shot.etag });
  }),

  http.post(API("/video-shots/:shotId/generate"), async ({ params, request }) => {
    await simulateLatency(150);
    const denied = requireSession();
    if (denied) return denied;
    const shot = db.shots.get(params.shotId as string);
    if (!shot) return notFound("镜头");
    const vp = db.videoProjects.get(shot.video_project_id);
    const lesson = vp ? db.lessons.get(vp.lesson_id) : null;
    if (!vp || !lesson) return notFound("视频项目");
    if (shot.status === "generating") {
      return fail(409, "SHOT_BUSY", "该镜头正在生成中。");
    }
    return idempotent(request, `shot-gen:${shot.id}`, () => {
      shot.status = "generating";
      shot.failure_reason = null;
      const nodeRun = [...db.nodeRuns.values()].find(
        (run) => run.lesson_id === lesson.id && run.node_key === "video_clips",
      );
      const job = startJob({
        kind: "video_shot",
        title: `生成镜头${shot.position}候选`,
        projectId: lesson.project_id,
        lessonId: lesson.id,
        nodeRunId: null,
        totalItems: 1,
        phaseMs: [900, 3000],
        onComplete: () => {
          produceResults({
            nodeRunId: nodeRun?.id ?? null,
            itemKey: shot.shot_key,
            mediaType: "video",
            count: 2,
            labelPrefix: `镜头${shot.position}`,
            durationSeconds: shot.shot.duration_seconds,
          });
          shot.status = "review_required";
          shot.active_job_id = null;
          emitEvent({
            event_type: "video_shot.candidates_ready",
            project_id: lesson.project_id,
            resource: { type: "video_shot", id: shot.id },
          });
        },
      });
      shot.active_job_id = job.id;
      return {
        data: { job_id: job.id, status: "queued", events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
        status: 202,
      };
    });
  }),
];
