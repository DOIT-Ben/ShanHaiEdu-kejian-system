import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  LessonDivisionDocument,
  LessonDivisionDraftEditor,
} from "@/features/lessons/components/LessonDivisionDocument";

const content = {
  coverage_check: {
    all_evidence_covered: true,
    overlap_free: true,
    progression_rationale: "由直观经验进入数字表示。",
    unresolved_questions: ["确认课堂是否配有数字卡片"],
  },
  lesson_count: 1,
  lesson_units: [
    {
      lesson_type: "new_learning",
      lesson_unit_key: "LESSON-001",
      title: "1～5的认识",
    },
  ],
};

describe("LessonDivisionDocument", () => {
  it("shows unresolved questions instead of hiding a blocking quality fact", () => {
    render(<LessonDivisionDocument content={content} />);

    expect(screen.getByRole("heading", { name: "待确认问题" })).toBeVisible();
    expect(screen.getByText("确认课堂是否配有数字卡片")).toBeVisible();
  });

  it("lets the teacher resolve questions in the saved draft", () => {
    const onChange = vi.fn();
    render(<LessonDivisionDraftEditor content={content} onChange={onChange} />);

    fireEvent.change(screen.getByRole("textbox", { name: "待确认问题（每行一项）" }), {
      target: { value: "" },
    });

    expect(onChange).toHaveBeenCalledWith({
      ...content,
      coverage_check: {
        ...content.coverage_check,
        unresolved_questions: [],
      },
    });
  });
});
