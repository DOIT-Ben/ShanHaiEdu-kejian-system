import type {
  TextbookEvidenceContent,
  DivisionContent,
  LessonPlanContent,
  IntroDesignContent,
  PptOutlineContent,
  PptPagesContent,
  PptExportContent,
  MasterScriptContent,
  VisualDirectionContent,
  MasterImageContent,
  RoughStoryboardContent,
  ImageAssetsContent,
  FineStoryboardContent,
  ShotPromptsContent,
  ClipsContent,
  AudioSubtitleContent,
  FinalCutContent,
} from "@/entities/content";
import { LESSON_PLAN_SECTIONS } from "@/entities/content";

/**
 * 「分数的初步认识」示范内容构造器。
 * 内容为确定性数据（无随机），供 Mock 与测试共用。
 */

export function buildEvidenceContent(options?: { partial?: boolean }): TextbookEvidenceContent {
  const partial = options?.partial ?? false;
  return {
    source_file_name: "人教版三年级上册数学教材.pdf",
    page_count: 6,
    summary: "第八单元「分数的初步认识」：认识几分之一、几分之几，简单比较分数大小与同分母加减。",
    pages: [
      {
        page_number: 89,
        title: "单元导入",
        ocr_text: "把一个月饼平均分成两份，每份是它的一半，也就是它的二分之一，写作 1/2。",
        low_confidence: false,
        blocks: [
          { type: "heading", text: "8 分数的初步认识", confidence: 0.99 },
          { type: "paragraph", text: "把一个月饼平均分成两份，每份是它的一半，也就是它的二分之一，写作 1/2。", confidence: 0.98 },
          { type: "figure", text: "插图：两名学生平分一个月饼", confidence: 0.92 },
        ],
      },
      {
        page_number: 90,
        title: "认识几分之一",
        ocr_text: "像 1/2、1/3、1/4 这样的数，都是分数。分数中间的横线叫分数线。",
        low_confidence: false,
        blocks: [
          { type: "paragraph", text: "像 1/2、1/3、1/4 这样的数，都是分数。", confidence: 0.97 },
          { type: "example", text: "例1：把一张正方形纸对折两次，涂色部分是这张纸的几分之一？", confidence: 0.95 },
        ],
      },
      {
        page_number: 91,
        title: "几分之一的大小比较",
        ocr_text: "同样大的圆，平均分的份数越多，每一份就越小。1/2 > 1/3 > 1/4。",
        low_confidence: partial,
        blocks: [
          { type: "example", text: "例2：比较 1/2 和 1/4 的大小。", confidence: partial ? 0.62 : 0.96 },
          { type: "figure", text: "插图：两个同样大的圆分别平均分成2份和4份", confidence: partial ? 0.58 : 0.93 },
        ],
      },
      {
        page_number: 92,
        title: "认识几分之几",
        ocr_text: "把一个整体平均分成若干份，表示这样的几份的数，叫做分数。3/4 表示把整体平均分成4份，取其中3份。",
        low_confidence: false,
        blocks: [
          { type: "paragraph", text: "3/4 表示把整体平均分成 4 份，取其中的 3 份。", confidence: 0.97 },
          { type: "example", text: "例3：涂色表示 2/5、3/5。", confidence: 0.96 },
        ],
      },
      {
        page_number: 93,
        title: "同分母分数加减",
        ocr_text: "2/5 + 1/5 = 3/5。分母不变，分子相加。",
        low_confidence: partial,
        blocks: [
          { type: "example", text: "例4：2/5 + 1/5 = ？", confidence: partial ? 0.55 : 0.95 },
          { type: "formula", text: "2/5 + 1/5 = 3/5", confidence: partial ? 0.6 : 0.98 },
        ],
      },
      {
        page_number: 94,
        title: "练习二十",
        ocr_text: "1. 用分数表示下面各图的涂色部分。2. 比较大小。3. 计算。",
        low_confidence: false,
        blocks: [
          { type: "exercise", text: "1. 用分数表示下面各图的涂色部分。", confidence: 0.96 },
          { type: "exercise", text: "2. 在 ○ 里填上 > 、< 或 =：1/3 ○ 1/4，2/5 ○ 3/5。", confidence: 0.95 },
        ],
      },
    ],
  };
}

export function buildDivisionContent(): DivisionContent {
  return {
    rationale:
      "依据教材第八单元结构，将「分数的初步认识」划分为 3 个课时：先建立几分之一的概念，再扩展到几分之几，最后学习同分母加减并综合练习。",
    lessons: [
      {
        lesson_key: "L1",
        title: "认识几分之一",
        lesson_type: "new_knowledge",
        duration_minutes: 40,
        knowledge_points: ["平均分", "二分之一的含义", "几分之一的读写", "几分之一的大小比较"],
        textbook_pages: "P89-91",
        objectives: "结合具体情境初步认识几分之一，会读写几分之一，能比较分子是1的分数大小。",
      },
      {
        lesson_key: "L2",
        title: "认识几分之几",
        lesson_type: "new_knowledge",
        duration_minutes: 40,
        knowledge_points: ["几分之几的含义", "分数各部分名称", "同分母分数大小比较"],
        textbook_pages: "P92-93",
        objectives: "理解几分之几的含义，认识分数各部分名称，会比较同分母分数的大小。",
      },
      {
        lesson_key: "L3",
        title: "分数的简单计算与练习",
        lesson_type: "practice",
        duration_minutes: 40,
        knowledge_points: ["同分母分数加法", "同分母分数减法", "1减几分之几"],
        textbook_pages: "P93-94",
        objectives: "掌握同分母分数（分母小于10）的加减法，能解决简单的实际问题。",
      },
    ],
  };
}

export function buildLessonPlanContent(lessonTitle: string, variant: 1 | 2 = 1): LessonPlanContent {
  const revised = variant === 2;
  const textBodies: Record<string, string> = {
    teaching_objectives: `1. 结合具体情境，初步理解${lessonTitle.includes("几分之一") ? "几分之一" : "分数"}的含义，会读、写简单的分数。
2. 经历「平均分—表示—比较」的探究过程，发展数感与几何直观。
3. 感受分数与生活的联系，激发学习数学的兴趣。${revised ? "\n4.（修订）增加对「平均分」前提条件的强调，突出概念本质。" : ""}`,
    core_competencies: "数感、几何直观、推理意识。通过折一折、涂一涂的操作活动，建立分数概念的直观模型。",
    learner_analysis:
      "三年级学生已掌握整数四则运算与「平均分」的经验，首次接触分数这一新的数概念。学生容易忽略「平均分」这一前提，需要通过对比辨析强化。",
    key_points: "理解几分之一的含义：把一个物体平均分成几份，每份是它的几分之一。",
    difficult_points: "理解「平均分」是分数产生的前提；理解分的份数越多、每份越小的道理。",
    preparation: "月饼图片、圆形纸片、长方形纸条、彩笔、课件（含导入视频）。",
    intro_hook: revised
      ? "播放导入视频《月饼分一分》（修订：将情境从郊游改为中秋分月饼，更贴近教材原型），提出问题：把一个月饼分给两个小朋友，怎样分才公平？"
      : "播放导入视频，提出问题：把一个月饼分给两个小朋友，怎样分才公平？引出「平均分」，当每人分到的不足一个时，如何表示？",
    board_design: `课题：认识几分之一
- 把一个月饼【平均分】成 2 份
- 每份是它的二分之一，写作 1/2
- 1/2 > 1/3 > 1/4（分的份数越多，每一份越小）`,
    exercise_design: "1. 基础练习：用分数表示涂色部分（教材P91做一做）。\n2. 变式练习：判断哪些分法能用 1/2 表示，为什么？\n3. 拓展练习：同样的正方形，折出不同的 1/4。",
    homework_design: "1. 完成练习二十第1、2题。\n2. 回家找一找生活中的「几分之一」，用图画记录下来，下节课分享。",
    reflection: "关注学生是否真正理解「平均分」前提；观察操作活动中是否出现将「份数」与「大小」混淆的情况，为下节课几分之几的学习做好铺垫。",
  };

  return {
    lesson_title: lessonTitle,
    sections: LESSON_PLAN_SECTIONS.map((section) => {
      if (section.kind === "process") {
        return {
          key: section.key,
          title: section.title,
          kind: "process" as const,
          body: "",
          stages: [
            {
              stage_id: "stage_1",
              stage_title: "情境导入，引出课题",
              minutes: 5,
              teacher_activity: "播放分月饼情境视频，提问：一半用一个什么样的数来表示？",
              student_activity: "观察情境，尝试用自己的方式表示「一半」。",
              design_intent: "从真实情境引发认知冲突，感受引入分数的必要性。",
            },
            {
              stage_id: "stage_2",
              stage_title: "动手操作，建构概念",
              minutes: 15,
              teacher_activity: "组织折纸活动：把圆形纸片平均分成2份、4份，指导涂色并表示。",
              student_activity: "折一折、涂一涂，用分数表示涂色部分，同桌互相说含义。",
              design_intent: "通过多元表征帮助学生建立几分之一的直观模型。",
            },
            {
              stage_id: "stage_3",
              stage_title: "对比辨析，深化理解",
              minutes: 12,
              teacher_activity: "呈现平均分与不平均分的对比图例，组织讨论：都能用 1/2 表示吗？",
              student_activity: "小组讨论、辨析，归纳「平均分」是使用分数的前提。",
              design_intent: "在辨析中突破难点，突出概念本质属性。",
            },
            {
              stage_id: "stage_4",
              stage_title: "分层练习，巩固应用",
              minutes: 6,
              teacher_activity: "布置分层练习，巡视指导，收集典型错误进行讲评。",
              student_activity: "独立完成练习，交流不同的折法与表示方法。",
              design_intent: "及时巩固，暴露并纠正典型错误。",
            },
            {
              stage_id: "stage_5",
              stage_title: "总结延伸，布置作业",
              minutes: 2,
              teacher_activity: "引导回顾：今天认识了什么样的数？它表示什么含义？",
              student_activity: "用自己的话总结几分之一的含义。",
              design_intent: "梳理知识结构，为认识几分之几做铺垫。",
            },
          ],
        };
      }
      return {
        key: section.key,
        title: section.title,
        kind: "text" as const,
        body: textBodies[section.key] ?? "",
        stages: [],
      };
    }),
  };
}

export function buildIntroDesignContent(options?: {
  anchorFailed?: boolean;
  selectedOptionId?: string | null;
  approvedOptionId?: string | null;
}): IntroDesignContent {
  const anchorFailed = options?.anchorFailed ?? false;
  const mk = (
    catKey: "science" | "application" | "story",
    _catName: string,
    optionNo: 1 | 2 | 3,
    title: string,
    summary: string,
    narrative: string,
    styleHint: string,
    anchorDesc: string,
  ) => ({
    option_id: `opt_${catKey}_${optionNo}`,
    option_no: optionNo,
    title,
    summary,
    narrative,
    style_hint: styleHint,
    duration_seconds: 90,
    anchors: [
      {
        anchor_id: `anchor_${catKey}_${optionNo}_1`,
        description: anchorDesc,
        knowledge_point: "平均分与二分之一的含义",
        status: (anchorFailed && catKey === "story" ? "failed" : "confirmed") as
          | "proposed"
          | "confirmed"
          | "failed",
      },
    ],
    status: (options?.approvedOptionId === `opt_${catKey}_${optionNo}`
      ? "approved"
      : anchorFailed && catKey === "story"
        ? "revision_required"
        : "needs_review") as "draft" | "needs_review" | "approved" | "rejected" | "revision_required",
    creative_locked: anchorFailed && catKey === "story",
  });

  return {
    selected_option_id: options?.selectedOptionId ?? options?.approvedOptionId ?? null,
    categories: [
      {
        category_key: "science",
        category_name: "科普向",
        options: [
          mk("science", "科普向", 1, "月亮的圆缺", "从月相变化引出「一半」与部分整体关系。", "动画演示满月逐渐变成半月，提问：现在我们能看到月亮的几分之几？", "手绘天文插画风", "由月亮的一半引出 1/2 的表示需求"),
          mk("science", "科普向", 2, "蜂巢的秘密", "观察蜂巢结构中的等分现象。", "镜头深入蜂巢，展示蜜蜂如何把蜂蜜平均储存在六边形格子里。", "自然纪录片风", "由蜂巢均分引出平均分概念"),
          mk("science", "科普向", 3, "身体里的分数", "心跳、呼吸中的节律等分。", "小科学家角色测量一分钟心跳，把时间平均分段观察。", "卡通科学实验室风", "由时间等分引出几分之一"),
        ],
      },
      {
        category_key: "application",
        category_name: "应用向",
        options: [
          mk("application", "应用向", 1, "分月饼", "中秋节分月饼的公平问题。", "两个小朋友要分一个月饼，怎么分才公平？切开后每人得到的还能用整数表示吗？", "温馨节日插画风", "平均分月饼直接对应例1情境"),
          mk("application", "应用向", 2, "披萨派对", "生日会上平分披萨。", "四个小朋友平分一个披萨，每人拿到一块，这一块是整个披萨的多少？", "明快扁平插画风", "由四等分引出 1/4"),
          mk("application", "应用向", 3, "折纸手工课", "折纸活动中的对折与等分。", "手工课上把彩纸对折再对折，展开后数一数被分成了几份。", "手作定格动画风", "对折操作对应折纸探究活动"),
        ],
      },
      {
        category_key: "story",
        category_name: "故事向",
        options: [
          mk("story", "故事向", 1, "熊猫兄弟分竹笋", "熊猫兄弟因分竹笋不均吵架。", "熊猫哥哥把竹笋掰成大小不一的两段被弟弟抗议，熊猫妈妈教它们平均分。", "国风水墨动画", "「分得不一样多」制造认知冲突"),
          mk("story", "故事向", 2, "小狐狸的蛋糕店", "小狐狸学习把蛋糕切均匀。", "小狐狸开蛋糕店，顾客要求「半个蛋糕」，它必须学会平均切分。", "绘本童话风", "「一半怎么表示」引出 1/2"),
          mk("story", "故事向", 3, "巨人的面包", "小人国平分巨人的面包。", "小人国捡到巨人的面包，国王下令平均分给全城居民。", "奇幻冒险动画风", "由多份等分引出几分之一"),
        ],
      },
    ],
  };
}

export function buildPptOutlineContent(lessonTitle: string): PptOutlineContent {
  return {
    lesson_title: lessonTitle,
    estimated_page_count: 14,
    sections: [
      { section_id: "sec_1", title: "课题与导入", page_titles: ["封面：认识几分之一", "情境导入：分月饼"] },
      { section_id: "sec_2", title: "探究新知", page_titles: ["平均分与一半", "认识 1/2", "折一折：认识 1/4", "分数的读写", "认识其他几分之一"] },
      { section_id: "sec_3", title: "深化理解", page_titles: ["辨一辨：是平均分吗", "比一比：1/2 和 1/4", "分的份数越多每份越小"] },
      { section_id: "sec_4", title: "巩固练习", page_titles: ["基础练习", "变式练习", "拓展挑战"] },
      { section_id: "sec_5", title: "课堂小结", page_titles: ["今天我们学会了"] },
    ],
  };
}

export function buildPptPagesContent(lessonTitle: string): PptPagesContent {
  const mkPage = (
    no: number,
    title: string,
    layout: "cover" | "section" | "content" | "example" | "exercise" | "summary",
    blocks: Array<{ type: "heading" | "text" | "bullets" | "image" | "formula" | "example" | "interaction"; text?: string; items?: string[] }>,
    notes: string,
  ) => ({
    page_id: `page_${no}`,
    page_no: no,
    title,
    layout,
    blocks: blocks.map((b, i) => ({
      block_id: `page_${no}_b${i + 1}`,
      type: b.type,
      text: b.text ?? "",
      items: b.items ?? [],
      asset_id: null,
    })),
    speaker_notes: notes,
    image_asset_ids: [],
    status: "needs_review" as const,
  });

  return {
    lesson_title: lessonTitle,
    theme: { cover_style: "designed", body_style: "pure_white", accent_color: "#2854E8" },
    pages: [
      mkPage(1, "认识几分之一", "cover", [{ type: "heading", text: "认识几分之一" }, { type: "text", text: "人教版三年级上册 · 第八单元" }], "开场问好，出示课题。"),
      mkPage(2, "情境导入：分月饼", "content", [{ type: "text", text: "中秋节到了，两个小朋友要分一个月饼。" }, { type: "interaction", text: "想一想：怎样分才公平？" }, { type: "image" }], "播放导入视频，引导学生说出「平均分」。"),
      mkPage(3, "平均分与一半", "content", [{ type: "text", text: "把一个月饼平均分成 2 份，每份是它的一半。" }, { type: "bullets", items: ["强调：必须平均分", "一半不能用整数表示"] }], "追问：一半该用什么数表示？"),
      mkPage(4, "认识 1/2", "content", [{ type: "formula", text: "一半 → 二分之一 → 写作 1/2" }, { type: "bullets", items: ["分数线：表示平均分", "分母 2：平均分成 2 份", "分子 1：表示这样的 1 份"] }, { type: "image" }], "板书 1/2，带读「二分之一」。"),
      mkPage(5, "折一折：认识 1/4", "example", [{ type: "example", text: "把一张正方形纸对折两次，每份是它的几分之一？" }, { type: "interaction", text: "动手折一折，涂出它的 1/4。" }], "组织折纸活动，展示不同折法。"),
      mkPage(6, "分数的读写", "content", [{ type: "bullets", items: ["先写分数线", "再写分母", "最后写分子"] }, { type: "formula", text: "1/3 读作：三分之一" }], "示范书写顺序。"),
      mkPage(7, "认识其他几分之一", "content", [{ type: "text", text: "生活中还有哪些几分之一？" }, { type: "image" }], "让学生举例。"),
      mkPage(8, "辨一辨：是平均分吗", "example", [{ type: "example", text: "下面的涂色部分能用 1/2 表示吗？为什么？" }, { type: "image" }], "呈现不平均分反例，组织辨析。"),
      mkPage(9, "比一比：1/2 和 1/4", "example", [{ type: "example", text: "同样大的圆，1/2 和 1/4 哪个大？" }, { type: "image" }], "引导观察比较。"),
      mkPage(10, "分的份数越多每份越小", "content", [{ type: "formula", text: "1/2 > 1/3 > 1/4" }, { type: "text", text: "同一个物体，平均分的份数越多，每一份就越小。" }], "总结规律。"),
      mkPage(11, "基础练习", "exercise", [{ type: "text", text: "用分数表示下面各图的涂色部分。" }, { type: "image" }], "独立完成后核对。"),
      mkPage(12, "变式练习", "exercise", [{ type: "text", text: "在 ○ 里填上 > 或 <：1/3 ○ 1/4　1/2 ○ 1/5" }], "请学生说理由。"),
      mkPage(13, "拓展挑战", "exercise", [{ type: "text", text: "同样的正方形，你能折出几种不同的 1/4 吗？" }], "鼓励多样化折法。"),
      mkPage(14, "今天我们学会了", "summary", [{ type: "bullets", items: ["平均分才能用分数表示", "几分之一的含义与读写", "分的份数越多，每一份越小"] }], "带领学生回顾。"),
    ],
  };
}

export function buildPptExportContent(fileObjectId: string | null): PptExportContent {
  return {
    file_object_id: fileObjectId,
    page_count: 14,
    exported_at: fileObjectId ? new Date().toISOString() : null,
    warnings: [],
  };
}

export function buildMasterScriptContent(introTitle: string): MasterScriptContent {
  return {
    intro_option_id: "opt_application_1",
    intro_option_title: introTitle,
    total_duration_seconds: 90,
    scenes: [
      { scene_id: "scene_1", scene_no: 1, title: "中秋团圆", narration: "中秋节的晚上，月亮又大又圆，乐乐和贝贝收到了一个香喷喷的月饼。", visual_idea: "温馨的庭院夜景，圆月当空，两个孩子捧着月饼", anchor_id: null, duration_seconds: 15 },
      { scene_id: "scene_2", scene_no: 2, title: "怎么分才公平", narration: "一个月饼，两个人吃，怎么分才公平呢？乐乐说：我要大的那块！贝贝不高兴了。", visual_idea: "两个孩子对着月饼比划，出现大小不一的切分虚线", anchor_id: null, duration_seconds: 20 },
      { scene_id: "scene_3", scene_no: 3, title: "平均分", narration: "妈妈笑着说：把月饼平均分成两份，每人一份，才公平。", visual_idea: "刀沿直径切下，月饼分成完全一样的两半", anchor_id: "anchor_application_1_1", duration_seconds: 20 },
      { scene_id: "scene_4", scene_no: 4, title: "一半是多少", narration: "每人分到一半。一半，还能用我们学过的 1、2、3 这些数表示吗？", visual_idea: "半块月饼特写，旁边浮现问号和整数序列", anchor_id: "anchor_application_1_1", duration_seconds: 20 },
      { scene_id: "scene_5", scene_no: 5, title: "引出新朋友", narration: "今天，我们要认识一位新朋友——分数。一起走进分数的世界吧！", visual_idea: "「1/2」符号闪亮登场，标题「认识几分之一」", anchor_id: null, duration_seconds: 15 },
    ],
  };
}

export function buildVisualDirectionContent(): VisualDirectionContent {
  return {
    style_name: "温暖手绘绘本风",
    style_keywords: ["柔和水彩质感", "圆润造型", "暖色月光", "儿童绘本"],
    palette: ["#FFB74D", "#FFE0B2", "#4A6FA5", "#2C3E66", "#FFF8E7"],
    character_notes: "乐乐：短发男孩，橙色上衣；贝贝：双马尾女孩，蓝色裙子；妈妈：温柔长发，米色围裙。角色比例 Q 版 2.5 头身。",
    scene_notes: "统一为中秋夜庭院场景：石桌、灯笼、桂花树，天空有大圆月；室内镜头为暖黄灯光餐厅。",
    reference_asset_ids: [],
  };
}

export function buildMasterImageContent(candidates: Array<{ candidateId: string; assetId: string; summary: string }>, selectedAssetId: string | null): MasterImageContent {
  return {
    candidates: candidates.map((c) => ({
      candidate_id: c.candidateId,
      asset_id: c.assetId,
      prompt_summary: c.summary,
      selected: c.assetId === selectedAssetId,
    })),
    selected_asset_id: selectedAssetId,
  };
}

export const ROUGH_SHOTS: Array<{ shotNo: number; sceneId: string; sceneTitle: string; description: string; camera: string; duration: number; narration: string }> = [
  { shotNo: 1, sceneId: "scene_1", sceneTitle: "中秋团圆", description: "庭院全景：圆月当空，桂花树下石桌，两个孩子跑向桌上的月饼", camera: "远景缓推", duration: 8, narration: "中秋节的晚上，月亮又大又圆。" },
  { shotNo: 2, sceneId: "scene_1", sceneTitle: "中秋团圆", description: "月饼特写：印着花纹的月饼冒着香气", camera: "特写", duration: 7, narration: "乐乐和贝贝收到了一个香喷喷的月饼。" },
  { shotNo: 3, sceneId: "scene_2", sceneTitle: "怎么分才公平", description: "两个孩子隔着月饼对视，头顶冒出大小不一的切分想象泡泡", camera: "中景", duration: 10, narration: "一个月饼，两个人吃，怎么分才公平呢？" },
  { shotNo: 4, sceneId: "scene_2", sceneTitle: "怎么分才公平", description: "贝贝鼓起脸颊不高兴，乐乐抱着月饼护住", camera: "近景切换", duration: 10, narration: "乐乐说：我要大的那块！贝贝不高兴了。" },
  { shotNo: 5, sceneId: "scene_3", sceneTitle: "平均分", description: "妈妈把刀对准月饼中心线，虚线提示平均分", camera: "俯拍", duration: 10, narration: "把月饼平均分成两份，每人一份，才公平。" },
  { shotNo: 6, sceneId: "scene_3", sceneTitle: "平均分", description: "月饼分成完全相同的两半，左右对称摆放，出现「平均分」字样", camera: "俯拍定格", duration: 10, narration: "这样的分法，叫做平均分。" },
  { shotNo: 7, sceneId: "scene_4", sceneTitle: "一半是多少", description: "半块月饼放大，旁边浮现 1、2、3 整数依次摇头消失，问号出现", camera: "特写+动效", duration: 20, narration: "一半，还能用学过的数表示吗？" },
  { shotNo: 8, sceneId: "scene_5", sceneTitle: "引出新朋友", description: "「1/2」符号发光登场，化作课题「认识几分之一」", camera: "中心汇聚", duration: 15, narration: "今天我们要认识新朋友——分数！" },
];

export function buildRoughStoryboardContent(): RoughStoryboardContent {
  return {
    shots: ROUGH_SHOTS.map((s) => ({
      shot_id: `shot_${s.shotNo}`,
      shot_no: s.shotNo,
      scene_id: s.sceneId,
      scene_title: s.sceneTitle,
      description: s.description,
      camera: s.camera,
      duration_seconds: s.duration,
      narration: s.narration,
    })),
  };
}

export function buildImageAssetsContent(
  items: Array<{ imageId: string; assetId: string | null; shotIds: string[]; summary: string; failed?: boolean }>,
): ImageAssetsContent {
  return {
    items: items.map((item) => ({
      image_id: item.imageId,
      asset_id: item.assetId,
      shot_ids: item.shotIds,
      prompt_summary: item.summary,
      based_on_master_image: true,
      status: item.failed ? "failed" : item.assetId ? "completed" : "pending",
      error_message: item.failed ? "图片生成服务返回内容安全校验失败，可调整提示词后重试。" : null,
    })),
  };
}

export function buildFineStoryboardContent(firstFrameByShot: Record<string, string | null>): FineStoryboardContent {
  return {
    shots: ROUGH_SHOTS.map((s) => ({
      shot_id: `shot_${s.shotNo}`,
      shot_no: s.shotNo,
      scene_title: s.sceneTitle,
      description: s.description,
      first_frame_asset_id: firstFrameByShot[`shot_${s.shotNo}`] ?? null,
      motion_notes: s.shotNo % 2 === 0 ? "镜头缓慢推近，角色轻微呼吸感" : "镜头固定，元素依次浮现",
      camera: s.camera,
      dialogue: s.narration,
      subtitle_text: s.narration,
      duration_seconds: s.duration,
    })),
  };
}

export function buildShotPromptsContent(firstFrameByShot: Record<string, string | null>): ShotPromptsContent {
  return {
    prompts: ROUGH_SHOTS.map((s) => ({
      shot_id: `shot_${s.shotNo}`,
      shot_no: s.shotNo,
      prompt_text: `温暖手绘绘本风，中秋夜庭院场景。${s.description}。镜头：${s.camera}，时长 ${s.duration} 秒。保持与视觉母图一致的角色造型与色板（#FFB74D 暖橙、#4A6FA5 月夜蓝）。画面适合小学三年级学生，明亮温馨。`,
      negative_prompt: "文字错误、肢体畸形、阴暗恐怖元素、真人写实",
      first_frame_asset_id: firstFrameByShot[`shot_${s.shotNo}`] ?? null,
      model_hint: "video_generation",
    })),
  };
}

export function buildClipsContent(
  clips: Array<{ clipId: string; shotId: string; shotNo: number; status: "queued" | "generating" | "completed" | "failed" | "approved"; assetId?: string | null; duration?: number; attempt?: number; error?: string | null }>,
): ClipsContent {
  return {
    clips: clips.map((c) => ({
      clip_id: c.clipId,
      shot_id: c.shotId,
      shot_no: c.shotNo,
      attempt: c.attempt ?? 1,
      status: c.status,
      video_asset_id: c.assetId ?? null,
      duration_seconds: c.duration ?? 0,
      error_message: c.error ?? null,
    })),
  };
}

export function buildAudioSubtitleContent(audioAssetId: string | null, subtitleAssetId: string | null): AudioSubtitleContent {
  let cursor = 0;
  const segments = ROUGH_SHOTS.map((s) => {
    const seg = { start_seconds: cursor, end_seconds: cursor + s.duration, text: s.narration };
    cursor += s.duration;
    return seg;
  });
  return {
    voice_name: "亲切童声（女）",
    audio_asset_id: audioAssetId,
    subtitle_asset_id: subtitleAssetId,
    segments,
  };
}

export function buildFinalCutContent(videoAssetId: string | null): FinalCutContent {
  return {
    video_asset_id: videoAssetId,
    duration_seconds: 90,
    resolution: "1920x1080",
    size_bytes: 48_500_000,
    included_shot_ids: ROUGH_SHOTS.map((s) => `shot_${s.shotNo}`),
  };
}
