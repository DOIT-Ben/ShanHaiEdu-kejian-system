import { describe, expect, it } from "vitest";
import { sortByRecommendation, groupByCategory, type IntroOption } from "./introOptions";
import { validatePageCanvas, type PptPageSpec } from "./pptPage";
import { checkAssetUsageConsistency, type VideoShot } from "./videoShot";

function option(partial: Partial<IntroOption>): IntroOption {
  return {
    option_key: "science_a",
    category: "science",
    title: "示例",
    independent_concept: "概念",
    hook: "钩子",
    course_anchor: "锚点",
    classroom_first_question: "第一问",
    handoff_moment: "交接",
    recommendation_score: 50,
    duration_seconds: 90,
    ...partial,
  } as IntroOption;
}

describe("三类九套：排序与分组", () => {
  it("按推荐分数降序排列", () => {
    const sorted = sortByRecommendation([
      option({ option_key: "a", recommendation_score: 60 }),
      option({ option_key: "b", recommendation_score: 90 }),
      option({ option_key: "c", recommendation_score: 75 }),
    ]);
    expect(sorted.map((o) => o.option_key)).toEqual(["b", "c", "a"]);
  });

  it("groupByCategory 保留三个类别的空数组", () => {
    const grouped = groupByCategory([option({ category: "story", option_key: "s1" })]);
    expect(grouped.story).toHaveLength(1);
    expect(grouped.science).toHaveLength(0);
    expect(grouped.application).toHaveLength(0);
  });
});

function pageSpec(partial: {
  page_type: PptPageSpec["page_type"];
  background_mode: "cover_art" | "solid_white";
  background_color?: string;
}): PptPageSpec {
  return {
    page_key: "PAGE-01",
    position: 1,
    page_type: partial.page_type,
    teaching_task: "任务",
    source_refs: [],
    student_focus: "焦点",
    canvas: {
      aspect_ratio: "16:9",
      background_mode: partial.background_mode,
      background_color: partial.background_color ?? "#FFFFFF",
      safe_area: { top: 0, right: 0, bottom: 0, left: 0 },
    },
    visual: {
      visual_decision: "quantity_relation",
      image_strategy: "none",
      main_visual_description: "",
      asset_requirements: [],
    },
    editable_text_blocks: [],
    editable_math_shapes: [],
    layout_spec: {},
    interaction_spec: {},
  } as unknown as PptPageSpec;
}

describe("PPT 画布规则（contracts/ppt-page-spec）", () => {
  it("封面必须 cover_art", () => {
    expect(validatePageCanvas(pageSpec({ page_type: "cover", background_mode: "cover_art" }))).toBeNull();
    expect(validatePageCanvas(pageSpec({ page_type: "cover", background_mode: "solid_white" }))).toMatch(/封面/);
  });

  it("正文必须纯白 #FFFFFF", () => {
    expect(validatePageCanvas(pageSpec({ page_type: "practice", background_mode: "solid_white" }))).toBeNull();
    expect(validatePageCanvas(pageSpec({ page_type: "practice", background_mode: "cover_art" }))).toMatch(/纯白/);
    expect(
      validatePageCanvas(pageSpec({ page_type: "practice", background_mode: "solid_white", background_color: "#F5F7FB" })),
    ).toMatch(/#FFFFFF/);
  });
});

function shot(partial: Partial<VideoShot>): VideoShot {
  return {
    shot_id: "SHOT-01",
    scene_id: "SCENE-01",
    position: 1,
    duration_seconds: 10,
    visible_beat: "beat",
    start_state: "start",
    end_state: "end",
    camera: { framing: "全景", angle: "平视", movement: "固定", start_composition: "a", end_composition: "b" },
    asset_usages: [],
    prompt_text: "画面描述",
    ...partial,
  } as VideoShot;
}

describe("镜头合同：垫图一致性（VIDEO_PRODUCTION §7）", () => {
  it("垫图序号连续且提示词包含 [图N] 时通过", () => {
    const ok = shot({
      asset_usages: [
        { image_index: 1, asset_version_id: "av-1", semantic_name: "松鼠", purpose: "主体" },
        { image_index: 2, asset_version_id: "av-2", semantic_name: "巧克力", purpose: "道具" },
      ],
      prompt_text: "参考[图1]松鼠与[图2]巧克力，镜头缓慢推近。",
    });
    expect(checkAssetUsageConsistency(ok)).toEqual([]);
  });

  it("序号断档与缺少 [图N] 标记都会报告", () => {
    const bad = shot({
      asset_usages: [
        { image_index: 1, asset_version_id: "av-1", semantic_name: "松鼠", purpose: "主体" },
        { image_index: 3, asset_version_id: "av-2", semantic_name: "巧克力", purpose: "道具" },
      ],
      prompt_text: "参考[图1]松鼠。",
    });
    const problems = checkAssetUsageConsistency(bad);
    expect(problems.some((p) => p.includes("连续编号"))).toBe(true);
    expect(problems.some((p) => p.includes("[图3]"))).toBe(true);
  });
});
