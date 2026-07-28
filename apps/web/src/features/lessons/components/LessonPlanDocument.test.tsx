import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  LessonPlanDocument,
  LessonPlanDraftEditor,
} from "@/features/lessons/components/LessonPlanDocument";

const content = {
  teaching_content: { teaching_scope: "认识百分数的意义" },
  material_analysis: { teaching_value: "建立百分数概念" },
  learner_analysis: { prior_learning: "已经理解分数意义" },
  design_intent: { process_design_rationale: "从真实情境建立概念" },
  teaching_objectives: { observable_outcome: "能够正确读写百分数" },
  key_difficulties_and_strategies: { key_learning_focus: "理解百分数表示关系" },
  preparation: { content_boundary: "不涉及百分数应用题" },
  teaching_process: [{ process_title: "情境导入", expected_responses: "发现比较困难" }],
  board_design: { board_final_content: "百分数表示两个量之间的关系" },
  lesson_summary: { teacher_closure: "回顾百分数的意义" },
  differentiated_homework: [{ homework_task: "完成基础练习" }],
  teaching_reflection: { reflection_prompts: "学生是否理解关系" },
};

describe("LessonPlanDocument", () => {
  it("renders all twelve teacher-facing sections", () => {
    render(<LessonPlanDocument content={content} />);

    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(12);
    expect(screen.getByRole("heading", { name: "一、教学内容" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "八、教学过程" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "十二、教学反思" })).toBeVisible();
    expect(screen.getByText("认识百分数的意义")).toBeVisible();
    expect(screen.getByText("学生是否理解关系")).toBeVisible();
    expect(screen.getByRole("region", { name: "一、教学内容" })).toHaveAttribute(
      "id",
      "lesson-plan-section-teaching_content",
    );
  });

  it("updates the exact nested body field without changing other sections", () => {
    const onChange = vi.fn();
    render(<LessonPlanDraftEditor content={content} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText("一、教学内容 教学范围 1"), {
      target: { value: "认识百分数并比较不同表示" },
    });

    expect(onChange).toHaveBeenCalledWith({
      ...content,
      teaching_content: { teaching_scope: "认识百分数并比较不同表示" },
    });
    const updated = onChange.mock.calls[0]?.[0] as typeof content | undefined;
    expect(updated?.learner_analysis).toEqual(content.learner_analysis);
  });

  it("keeps draft and submitted preview section ids unique in the same document", () => {
    const { container } = render(
      <>
        <LessonPlanDraftEditor
          content={content}
          idPrefix="lesson-plan-draft-section"
          onChange={vi.fn()}
        />
        <LessonPlanDocument content={content} idPrefix="lesson-plan-submitted-section" />
      </>,
    );

    const ids = Array.from(container.querySelectorAll("[id]"), (element) => element.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(container.querySelector("#lesson-plan-draft-section-teaching_content")).toBeVisible();
    expect(
      container.querySelector("#lesson-plan-submitted-section-teaching_content"),
    ).toBeVisible();
  });
});
