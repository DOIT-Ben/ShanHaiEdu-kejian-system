import { http } from "msw";
import { db, emitEvent, nextId, nowIso, touchLesson } from "../db";
import { API, checkIfMatch, fail, idempotent, notFound, ok, requireSession, simulateLatency } from "../http";

/** 三类九套：读取、允许字段修改、选择协议（选择即建不可变记录）。 */
export const introHandlers = [
  http.get(API("/lessons/:lessonId/intro-options"), async ({ params }) => {
    await simulateLatency(120);
    const denied = requireSession();
    if (denied) return denied;
    const state = db.introOptionSets.get(params.lessonId as string);
    if (!state) return notFound("导入设计");
    return ok(state.set, { etag: state.etag });
  }),

  http.patch(API("/lessons/:lessonId/intro-options/:optionKey"), async ({ params, request }) => {
    await simulateLatency(140);
    const denied = requireSession();
    if (denied) return denied;
    const state = db.introOptionSets.get(params.lessonId as string);
    if (!state) return notFound("导入设计");
    const conflict = checkIfMatch(request, state.etag);
    if (conflict) return conflict;
    const option = state.set.options.find((o) => o.option_key === params.optionKey);
    if (!option) return notFound("方案");
    const body = (await request.json()) as Partial<{
      title: string;
      independent_concept: string;
      hook: string;
      course_anchor: string;
      classroom_first_question: string;
      handoff_moment: string;
      must_not_preteach: string[];
    }>;
    const allowed = [
      "title",
      "independent_concept",
      "hook",
      "course_anchor",
      "classroom_first_question",
      "handoff_moment",
      "must_not_preteach",
    ] as const;
    for (const key of allowed) {
      const value = body[key];
      if (value !== undefined) {
        // @ts-expect-error 键集合受 allowed 限制
        option[key] = value;
      }
    }
    state.etag += 1;
    return ok(state.set, { etag: state.etag });
  }),

  http.post(API("/lessons/:lessonId/intro-selections"), async ({ params, request }) => {
    await simulateLatency(200);
    const denied = requireSession();
    if (denied) return denied;
    const lessonId = params.lessonId as string;
    const lesson = db.lessons.get(lessonId);
    const state = db.introOptionSets.get(lessonId);
    if (!lesson || !state) return notFound("导入设计");
    const body = (await request.json()) as { intro_option_set_version_id?: string; option_key?: string };
    if (!body.intro_option_set_version_id || !body.option_key) {
      return fail(422, "VALIDATION_FAILED", "缺少方案信息。");
    }
    if (body.intro_option_set_version_id !== state.set.option_set_id) {
      return fail(409, "OPTION_SET_STALE", "九套方案已更新，请刷新后重新选择。");
    }
    const option = state.set.options.find((o) => o.option_key === body.option_key);
    if (!option) return notFound("方案");

    return idempotent(request, `intro-select:${lessonId}:${body.option_key}`, () => {
      const selection = {
        selection_id: nextId(),
        lesson_id: lessonId,
        option_set_version_id: state.set.option_set_id,
        option_key: option.option_key,
        choice_mode: "teacher_selected" as const,
        selected_at: nowIso(),
      };
      db.introSelections.set(lessonId, selection);
      state.set.status = "approved";
      state.etag += 1;
      lesson.branches.intro_options = {
        state: "approved",
        summary: `已选「${option.title}」`,
        next_step_key: null,
      };
      // 解锁视频链路（若启用）
      if (lesson.branches.video.state !== "disabled") {
        lesson.branches.video = {
          state: "in_progress",
          summary: "可以开始编写母版剧本",
          next_step_key: "video-script",
        };
        for (const run of db.nodeRuns.values()) {
          if (run.lesson_id === lessonId && run.node_key === "video_script" && run.status === "not_ready") {
            run.status = "ready";
            run.updated_at = nowIso();
          }
          if (run.lesson_id === lessonId && run.node_key === "intro_selection") {
            run.status = "approved";
            run.updated_at = nowIso();
          }
        }
      }
      touchLesson(lessonId);
      emitEvent({
        event_type: "intro_selection.created",
        project_id: lesson.project_id,
        resource: { type: "intro_selection", id: selection.selection_id },
        payload: { option_key: option.option_key },
      });
      return {
        data: {
          selection_id: selection.selection_id,
          option_set_version_id: selection.option_set_version_id,
          option_key: selection.option_key,
          choice_mode: selection.choice_mode,
          selected_at: selection.selected_at,
        },
        status: 201,
      };
    });
  }),

  http.get(API("/lessons/:lessonId/intro-selections/current"), async ({ params }) => {
    await simulateLatency(80);
    const denied = requireSession();
    if (denied) return denied;
    const selection = db.introSelections.get(params.lessonId as string);
    if (!selection) return ok(null);
    return ok({
      selection_id: selection.selection_id,
      option_set_version_id: selection.option_set_version_id,
      option_key: selection.option_key,
      choice_mode: selection.choice_mode,
      selected_at: selection.selected_at,
    });
  }),
];
