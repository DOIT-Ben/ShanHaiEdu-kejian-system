import { describe, expect, it } from "vitest";
import {
  divisionContentSchema,
  LESSON_PLAN_SECTIONS,
  lessonPlanContentSchema,
  parseContent,
  textbookEvidenceContentSchema,
} from "./index";

describe("parseContent", () => {
  it("合法内容返回解析结果", () => {
    const parsed = parseContent(divisionContentSchema, {
      lessons: [{ lesson_key: "l1", title: "认识几分之一" }],
    });
    expect(parsed).not.toBeNull();
    expect(parsed?.lessons[0].lesson_type).toBe("new_knowledge"); // 默认值
    expect(parsed?.lessons[0].duration_minutes).toBe(40);
  });

  it("结构不符返回 null 而不是抛错", () => {
    expect(parseContent(divisionContentSchema, { lessons: "oops" })).toBeNull();
    expect(parseContent(divisionContentSchema, null)).toBeNull();
    expect(parseContent(divisionContentSchema, undefined)).toBeNull();
  });
});

describe("textbookEvidenceContentSchema", () => {
  it("页面块默认空数组、低置信默认 false", () => {
    const parsed = textbookEvidenceContentSchema.parse({
      page_count: 1,
      pages: [{ page_number: 90, ocr_text: "分数的初步认识" }],
    });
    expect(parsed.pages[0].blocks).toEqual([]);
    expect(parsed.pages[0].low_confidence).toBe(false);
  });
});

describe("lessonPlanContentSchema", () => {
  it("必须包含全部十二个小节", () => {
    const full = {
      lesson_title: "认识几分之一",
      sections: LESSON_PLAN_SECTIONS.map((section) => ({
        key: section.key,
        title: section.title,
        kind: section.kind,
        body: "内容",
      })),
    };
    expect(lessonPlanContentSchema.safeParse(full).success).toBe(true);
    // 少一节即不合法
    expect(
      lessonPlanContentSchema.safeParse({ ...full, sections: full.sections.slice(0, 11) }).success,
    ).toBe(false);
  });
});
