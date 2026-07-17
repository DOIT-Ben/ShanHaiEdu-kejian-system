import type { ContentDefinition } from "@/entities/content/definition";
import type { IntroOptionSet } from "@/entities/content/introOptions";
import type { PptPageSpec } from "@/entities/content/pptPage";
import type { VideoShot } from "@/entities/content/videoShot";
import { uuid } from "./ids";

/**
 * 内容夹具：默认十二部分教案内容定义（仅默认，不是常量结构）、
 * 备用五部分简案定义（验证 Schema 切换）、三类九套、PPT 页、细分镜。
 */

export const lessonPlanDefinition: ContentDefinition = {
  definition_key: "primary_math.lesson_plan.default",
  title: "小学数学教案（默认十二部分）",
  fields: [
    { field_key: "teaching_content", label: "教学内容", type: "rich_text", required: true, editable: true, deletable: false },
    { field_key: "textbook_analysis", label: "教材分析", type: "rich_text", required: true, editable: true, deletable: false },
    { field_key: "learner_analysis", label: "学情分析", type: "rich_text", required: true, editable: true, deletable: false },
    { field_key: "design_intent", label: "设计意图", type: "rich_text", required: false, editable: true, deletable: true },
    { field_key: "teaching_goals", label: "教学目标", type: "list", required: true, editable: true, deletable: false },
    {
      field_key: "key_difficulties",
      label: "教学重难点及突破策略",
      type: "group",
      required: true,
      editable: true,
      deletable: false,
      children: [
        { field_key: "key_points", label: "教学重点", type: "list", required: true, editable: true, deletable: false },
        { field_key: "difficult_points", label: "教学难点", type: "list", required: true, editable: true, deletable: false },
        { field_key: "breakthrough", label: "突破策略", type: "rich_text", required: true, editable: true, deletable: false },
      ],
    },
    { field_key: "preparation", label: "教学准备", type: "list", required: false, editable: true, deletable: true },
    {
      field_key: "teaching_process",
      label: "教学过程",
      type: "repeatable",
      required: true,
      editable: true,
      deletable: false,
      repeatable: true,
      min_items: 3,
      children: [
        { field_key: "phase_title", label: "环节名称", type: "text", required: true, editable: true, deletable: false },
        { field_key: "duration_minutes", label: "时长（分钟）", type: "number", required: true, editable: true, deletable: false },
        { field_key: "teacher_activity", label: "教师活动", type: "rich_text", required: true, editable: true, deletable: false },
        { field_key: "student_activity", label: "学生活动", type: "rich_text", required: true, editable: true, deletable: false },
        { field_key: "intent", label: "设计意图", type: "rich_text", required: false, editable: true, deletable: true },
      ],
    },
    { field_key: "board_design", label: "板书设计", type: "rich_text", required: true, editable: true, deletable: false },
    { field_key: "summary", label: "课堂总结", type: "rich_text", required: true, editable: true, deletable: false },
    {
      field_key: "tiered_homework",
      label: "分层作业",
      type: "group",
      required: false,
      editable: true,
      deletable: true,
      children: [
        { field_key: "basic", label: "基础题", type: "list", required: true, editable: true, deletable: false },
        { field_key: "advanced", label: "提高题", type: "list", required: false, editable: true, deletable: true },
        { field_key: "challenge", label: "挑战题", type: "list", required: false, editable: true, deletable: true },
      ],
    },
    { field_key: "reflection", label: "教学反思", type: "rich_text", required: false, editable: true, deletable: true },
  ],
};

/** 备用简案定义：验证「两套 Schema 无需改页面代码即可切换」。 */
export const briefPlanDefinition: ContentDefinition = {
  definition_key: "primary_math.lesson_plan.brief",
  title: "小学数学简案（五部分）",
  fields: [
    { field_key: "teaching_goals", label: "教学目标", type: "list", required: true, editable: true, deletable: false },
    { field_key: "key_points", label: "重点难点", type: "rich_text", required: true, editable: true, deletable: false },
    {
      field_key: "process_timeline",
      label: "课堂流程",
      type: "timeline",
      required: true,
      editable: true,
      deletable: false,
    },
    { field_key: "board_design", label: "板书要点", type: "rich_text", required: false, editable: true, deletable: true },
    { field_key: "homework", label: "作业", type: "list", required: false, editable: true, deletable: true },
  ],
};

export const lessonPlanContent: Record<string, unknown> = {
  teaching_content: "人教版三年级上册第八单元：认识几分之几。通过折一折、涂一涂，理解把一个整体平均分成若干份，其中的几份可以用几分之几表示。",
  textbook_analysis:
    "本课时在「认识几分之一」的基础上展开。教材通过折纸涂色活动引出四分之三，再类推到其他分数，突出「平均分」与「份数关系」两条主线。",
  learner_analysis:
    "学生已经认识几分之一，能说出二分之一、四分之一的含义，但容易忽略「平均分」前提，也容易把分子与份数混淆。",
  design_intent: "以动手操作贯穿全课，让学生在折、涂、说的过程中自主建构几分之几的含义。",
  teaching_goals: [
    "结合具体情境认识几分之几，能读写简单分数。",
    "经历折纸、涂色的过程，理解分数中分子与分母的含义。",
    "感受分数与生活的联系，培养动手操作与表达能力。",
  ],
  key_difficulties: {
    key_points: ["理解几分之几的含义", "会读写简单分数"],
    difficult_points: ["理解分子、分母与平均分份数的对应关系"],
    breakthrough: "通过折一折、涂一涂、说一说三个层次活动，让每个学生都经历「平均分—取几份—用分数表示」的完整过程。",
  },
  preparation: ["每人 4 张正方形彩纸", "彩笔", "分数卡片", "课件"],
  teaching_process: [
    {
      phase_title: "情境导入",
      duration_minutes: 5,
      teacher_activity: "播放课堂导入视频/展示情境，提出问题：一张纸平均分成 4 份，涂了 3 份，涂色部分怎么表示？",
      student_activity: "观察、猜想，尝试用自己的方式表示。",
      intent: "从认知冲突出发引出新知。",
    },
    {
      phase_title: "动手探究",
      duration_minutes: 15,
      teacher_activity: "组织折纸涂色活动，巡视指导，追问「为什么必须平均分」。",
      student_activity: "折一折、涂一涂，展示不同折法，说出涂色部分表示的分数。",
      intent: "在操作中理解四分之三的含义。",
    },
    {
      phase_title: "抽象建构",
      duration_minutes: 10,
      teacher_activity: "引导比较不同分数，归纳分子、分母的含义，示范分数读写。",
      student_activity: "观察比较，尝试归纳，练习读写分数。",
      intent: "从具体到抽象，建立分数概念。",
    },
    {
      phase_title: "分层练习",
      duration_minutes: 8,
      teacher_activity: "出示分层练习，组织反馈交流。",
      student_activity: "独立完成练习，同桌互查，交流订正。",
      intent: "巩固新知，暴露并纠正典型错误。",
    },
    {
      phase_title: "总结延伸",
      duration_minutes: 4,
      teacher_activity: "引导回顾本课收获，布置分层作业。",
      student_activity: "用自己的话总结几分之几的含义。",
      intent: "梳理知识结构，为后续学习铺垫。",
    },
  ],
  board_design: "认识几分之几\n把一个整体平均分成 4 份 → 每份是它的 1/4 → 3 份是它的 3/4\n分母：平均分的份数；分子：取的份数",
  summary: "把一个整体平均分成若干份，取其中的几份，就可以用几分之几表示；分母表示平均分的份数，分子表示取的份数。",
  tiered_homework: {
    basic: ["课本第 92 页第 1、2 题", "用涂色表示 2/3、3/5"],
    advanced: ["找一找生活中能用几分之几表示的例子并记录"],
    challenge: ["同一张纸折出 3/4 的两种不同方法，并说明理由"],
  },
  reflection: "",
};

/** 校验产生一条警告：环节时长合计 42 分钟 > 40 分钟课时。 */
export const lessonPlanWarning = {
  key: "process_duration_over_limit",
  severity: "warning" as const,
  message: "教学过程各环节时长合计 42 分钟，超过课时 40 分钟，请压缩或说明。",
  field_path: "teaching_process",
};

export function buildIntroOptionSet(lessonId: string): IntroOptionSet {
  const options: IntroOptionSet["options"] = [
    {
      option_key: "INTRO-SCI-01",
      category: "science",
      title: "披萨店的失踪一角",
      independent_concept: "一整张披萨切成同样大的 4 块后少了 1 块，剩下部分的多少引发直观比较：剩下的还够几个人吃？",
      hook: "监控镜头回放：打烊前完整的披萨，清晨少了一角。",
      viewer_value: "即使不知道要学什么，观众也想知道少了多少、剩下多少，这是天然的份额直觉游戏。",
      suggested_medium: "video",
      duration_seconds: 90,
      replacement_field_key: "teaching_process.0",
      course_anchor: "剩下的 3 块正好可以用一个分数来准确表示——它和本课「几分之几」的表示法直接相连。",
      classroom_first_question: "剩下的披萨占整张的几分之几？怎样表示才准确？",
      handoff_moment: "店主拿出粉笔想在小黑板上写「还剩___张披萨」却卡住的瞬间。",
      must_not_preteach: ["分数的读写规则", "分子分母的定义"],
      fit_reason: "披萨即「平均分」的天然模型，切块贴合三年级生活经验，时长可控。",
      risks: ["学生可能纠结披萨口味等无关细节"],
      recommendation_score: 92,
      recommendation_reason: "情境完整、悬念自然、与平均分模型无缝衔接，制作成本低。",
    },
    {
      option_key: "INTRO-SCI-02",
      category: "science",
      title: "月亮为什么会缺一块",
      independent_concept: "连续七晚观察月亮，圆月一点点变成弯月：同一个月亮，看到的亮面每天不一样多。",
      hook: "延时摄影：一周内月亮从满月「瘦」成月牙。",
      viewer_value: "月相变化本身就是值得追问的自然奇观。",
      suggested_medium: "video",
      duration_seconds: 80,
      replacement_field_key: "teaching_process.0",
      course_anchor: "「亮面占整个月亮的多少」需要一种比「一半」更精细的说法。",
      classroom_first_question: "今晚的亮面大约占整个月亮的几分之几？",
      handoff_moment: "小观察员在记录本上画出月亮并想标注亮面大小时停笔。",
      must_not_preteach: ["分数符号写法", "平均分的严格定义"],
      fit_reason: "跨学科真实观察，能自然引出对份额的精细表达需求。",
      risks: ["月相成因超纲，需回避解释", "亮面并非严格平均分，需教师把握"],
      recommendation_score: 74,
      recommendation_reason: "观察性强，但份额不严格平均，回接时需要教师额外处理。",
    },
    {
      option_key: "INTRO-SCI-03",
      category: "science",
      title: "水杯里的刻度秘密",
      independent_concept: "同样的水倒进不同形状的杯子，看起来高低不同；带刻度的量杯却能说清「装了多少」。",
      hook: "两只杯子水位一高一低，倒回量杯竟然一样多。",
      viewer_value: "视觉错觉与测量真相的反差本身就有观看价值。",
      suggested_medium: "mixed",
      duration_seconds: 75,
      replacement_field_key: "teaching_process.0",
      course_anchor: "量杯上「4 格装了 3 格」的状态呼唤一个能表达部分与整体关系的数。",
      classroom_first_question: "水装到 4 格中的 3 格，用什么数表示最合适？",
      handoff_moment: "镜头定格在量杯 4 格刻度中水面停在第 3 格。",
      must_not_preteach: ["分数读写", "分母分子名称"],
      fit_reason: "测量情境规范，「格」即平均分的份，迁移干净。",
      risks: ["实验器材画面要求较高"],
      recommendation_score: 68,
      recommendation_reason: "科学性好，但钩子强度弱于披萨与月亮。",
    },
    {
      option_key: "INTRO-APP-01",
      category: "application",
      title: "生日蛋糕的公平切法",
      independent_concept: "4 个小伙伴分一个方形蛋糕，怎样切每人才拿得一样多？切好后又来了 1 个人，已切走的部分怎么描述？",
      hook: "生日会上刀落下前的争论：这样切公平吗？",
      viewer_value: "公平分配是儿童真实在意的问题，不学数学也想给出答案。",
      suggested_medium: "video",
      duration_seconds: 100,
      replacement_field_key: "teaching_process.0",
      course_anchor: "「已经拿走 4 份中的 3 份」正需要一个分数来准确记录。",
      classroom_first_question: "拿走的蛋糕占整个的几分之几？",
      handoff_moment: "妈妈问「拿走了多少」时，孩子们比划却说不清楚。",
      must_not_preteach: ["几分之几的定义", "分数大小比较"],
      fit_reason: "公平分配天然要求平均分，与本课模型完全一致。",
      risks: ["场景较常规，惊喜感一般"],
      recommendation_score: 85,
      recommendation_reason: "任务真实、参与感强、回接干净，是应用类最优。",
    },
    {
      option_key: "INTRO-APP-02",
      category: "application",
      title: "拼图进度条",
      independent_concept: "100 块拼图拼到一半多，怎样向朋友说清「拼到哪儿了」？只说「快了」显然不够。",
      hook: "视频通话里朋友追问：到底拼了多少？",
      viewer_value: "精确汇报进度是游戏玩家的真实需要。",
      suggested_medium: "image",
      duration_seconds: 60,
      replacement_field_key: "teaching_process.0",
      course_anchor: "把拼图平均分成 4 区、完成 3 区，「4 区中的 3 区」正是几分之几。",
      classroom_first_question: "完成的部分占整幅拼图的几分之几？",
      handoff_moment: "主角把拼图版图画成 4 大块、涂满 3 块后望向镜头。",
      must_not_preteach: ["分数符号", "百分数"],
      fit_reason: "进度表达贴近学生数字生活经验。",
      risks: ["100 块与 4 区的换算可能分散注意力"],
      recommendation_score: 66,
      recommendation_reason: "情境好但需要预先把 100 块抽象成 4 区，多一步转换。",
    },
    {
      option_key: "INTRO-APP-03",
      category: "application",
      title: "彩带够不够",
      independent_concept: "包装 4 个礼盒，一卷彩带用掉一部分后，剩下的还够包几个盒子？需要先说清用掉了多少。",
      hook: "手工课倒计时，彩带看起来不太够了。",
      viewer_value: "资源够不够的判断是真实的动手任务。",
      suggested_medium: "physical_object",
      duration_seconds: 70,
      replacement_field_key: "teaching_process.0",
      course_anchor: "把整卷彩带平均分成 4 段、已用 3 段的状态需要分数表达。",
      classroom_first_question: "用掉的彩带占整卷的几分之几？剩下的够包几个盒子？",
      handoff_moment: "彩带被平均折成 4 段、剪掉 3 段的特写。",
      must_not_preteach: ["分数加减", "几分之几定义"],
      fit_reason: "实物操作与本课折纸活动衔接顺滑。",
      risks: ["彩带长度视觉估计误差大"],
      recommendation_score: 61,
      recommendation_reason: "可操作性强，但悬念与传播力一般。",
    },
    {
      option_key: "INTRO-STO-01",
      category: "story",
      title: "巧克力守卫战",
      independent_concept: "小松鼠把一块巧克力平均分成 4 块藏进树洞，取回时发现只剩 1 块：小偷到底偷走了多少？",
      hook: "树洞前的爪印与散落的锡纸。",
      viewer_value: "悬疑侦探剧情：谁偷了巧克力、偷了多少，本身就想看下去。",
      suggested_medium: "video",
      duration_seconds: 110,
      replacement_field_key: "teaching_process.0",
      course_anchor: "「被偷走 4 块中的 3 块」需要一个精确的数来立案记录。",
      classroom_first_question: "被偷走的巧克力占整块的几分之几？",
      handoff_moment: "松鼠警长在案情板写下「失窃：？」的问号定格。",
      must_not_preteach: ["分数的读写", "分子分母含义"],
      fit_reason: "把平均分与取几份编入剧情主线，回接点唯一且清晰。",
      risks: ["动物角色造型需避免低幼化", "时长偏长需控制节奏"],
      recommendation_score: 88,
      recommendation_reason: "故事完整、动机强、与知识点结构同构，适合视频制作。",
    },
    {
      option_key: "INTRO-STO-02",
      category: "story",
      title: "环形跑道上的接力棒",
      independent_concept: "四人接力跑一圈，第三棒突然摔倒：比赛还剩下多少路程？裁判需要准确描述。",
      hook: "慢镜头：接力棒脱手滚向跑道边缘。",
      viewer_value: "比赛悬念与意外让观众关心「还剩多少」。",
      suggested_medium: "video",
      duration_seconds: 95,
      replacement_field_key: "teaching_process.0",
      course_anchor: "跑道被平均分成 4 段、已完成 3 段——剩余与完成都指向几分之几。",
      classroom_first_question: "已经跑完的路程占整圈的几分之几？",
      handoff_moment: "裁判举旗准备宣布进度却找不到合适说法。",
      must_not_preteach: ["分数定义", "分数比较"],
      fit_reason: "运动情境有天然的分段结构。",
      risks: ["摔倒画面需避免疼痛渲染"],
      recommendation_score: 71,
      recommendation_reason: "张力好，但「平均四段」的设定需要额外交代。",
    },
    {
      option_key: "INTRO-STO-03",
      category: "story",
      title: "彩虹桥修复记",
      independent_concept: "暴风雨吹坏了彩虹桥，小精灵们连夜修好了大部分，天亮前还差最后一段：修好的到底有多少？",
      hook: "云端俯瞰：彩虹桥缺口处闪烁的警示灯。",
      viewer_value: "修复任务的倒计时紧张感与幻想美术风格。",
      suggested_medium: "video",
      duration_seconds: 100,
      replacement_field_key: "teaching_process.0",
      course_anchor: "桥身被平均分为 4 段、修好 3 段，进度汇报需要分数。",
      classroom_first_question: "修好的部分占整座桥的几分之几？",
      handoff_moment: "精灵队长向月亮女王汇报进度时张口停顿。",
      must_not_preteach: ["分数读写规则"],
      fit_reason: "分段桥体是显性的平均分模型。",
      risks: ["幻想设定与教材情境距离较远", "美术成本高"],
      recommendation_score: 58,
      recommendation_reason: "画面美但制作成本高，回接不如侦探线直接。",
    },
  ];
  return {
    option_set_id: uuid(1401),
    lesson_unit_id: lessonId,
    status: "review_required",
    ideation_context_snapshot_id: uuid(1402),
    anchoring_context_snapshot_id: uuid(1403),
    options,
    created_at: "2026-07-16T02:30:00Z",
  };
}

function bodyPage(
  n: number,
  pageType: PptPageSpec["page_type"],
  teachingTask: string,
  visualDescription: string,
  blocks: { key: string; role: "title" | "body" | "question" | "label" | "answer" | "note"; text: string }[],
  shapes: PptPageSpec["editable_math_shapes"] = [],
): PptPageSpec {
  return {
    page_key: `PAGE-${String(n).padStart(2, "0")}`,
    position: n,
    page_type: pageType,
    teaching_task: teachingTask,
    source_refs: ["教案：教学过程", `教材第 ${88 + n} 页`],
    student_focus: teachingTask,
    canvas: {
      aspect_ratio: "16:9",
      background_mode: "solid_white",
      background_color: "#FFFFFF",
      safe_area: { top: 48, right: 64, bottom: 48, left: 64 },
    },
    visual: {
      visual_decision: "whole_part",
      image_strategy: "mixed",
      main_visual_description: visualDescription,
      asset_requirements: [
        {
          requirement_key: `PAGE-${String(n).padStart(2, "0")}-MAIN`,
          role: "main_visual",
          prompt: `${visualDescription}。手工纸艺质感，柔和自然光，白色背景，无任何文字数字。`,
          negative_prompt: "文字, 数字, 公式, 水印, Logo",
          target_slot_key: `ppt.page${n}.main_visual`,
        },
      ],
    },
    editable_text_blocks: blocks.map((b, i) => ({
      block_key: b.key,
      role: b.role,
      text: b.text,
      layout: { order: i + 1 },
    })),
    editable_math_shapes: shapes,
    layout_spec: { template: "visual_left_text_right" },
    interaction_spec: {},
    speaker_notes: "",
    validation_rules: [],
  };
}

export function buildPptPages(): PptPageSpec[] {
  const cover: PptPageSpec = {
    page_key: "PAGE-01",
    position: 1,
    page_type: "cover",
    teaching_task: "呈现课题，营造探究期待",
    source_refs: ["教案：教学内容"],
    student_focus: "今天我们研究什么",
    canvas: {
      aspect_ratio: "16:9",
      background_mode: "cover_art",
      safe_area: { top: 32, right: 48, bottom: 32, left: 48 },
    },
    visual: {
      visual_decision: "whole_part",
      image_strategy: "original_asset",
      main_visual_description: "俯拍木桌上被平均切成四块、取走三块的手工纸艺披萨，暖色灯光，留白构图",
      asset_requirements: [
        {
          requirement_key: "PAGE-01-COVER",
          role: "main_visual",
          prompt: "俯拍木桌上被平均切成四块、取走三块的手工纸艺披萨，暖色灯光，纸艺质感，大面积留白，无任何文字。",
          negative_prompt: "文字, 数字, 水印, 真实食物摄影",
          target_slot_key: "ppt.cover.main_visual",
        },
      ],
    },
    editable_text_blocks: [
      { block_key: "cover-title", role: "title", text: "认识几分之几", layout: { order: 1 } },
      { block_key: "cover-sub", role: "label", text: "三年级 · 数学", layout: { order: 2 } },
    ],
    editable_math_shapes: [],
    layout_spec: { template: "cover_center" },
    interaction_spec: {},
    speaker_notes: "开场直接指向披萨情境。",
    validation_rules: [],
  };
  return [
    cover,
    bodyPage(
      2,
      "introduction",
      "从披萨情境提出核心问题",
      "纸艺披萨平均分成四块、剩三块的桌面场景",
      [
        { key: "p2-title", role: "title", text: "剩下的披萨怎么表示？" },
        { key: "p2-q", role: "question", text: "一张披萨平均分成 4 块，拿走 1 块，剩下的部分怎么用一个数表示？" },
      ],
    ),
    bodyPage(
      3,
      "exploration",
      "折一折涂一涂表示四分之三",
      "四张展示不同折法的正方形彩纸，其中三格涂色",
      [
        { key: "p3-title", role: "title", text: "折一折 · 涂一涂" },
        { key: "p3-body", role: "body", text: "把正方形纸平均折成 4 份，给其中 3 份涂色。" },
        { key: "p3-q", role: "question", text: "涂色部分是这张纸的几分之几？" },
      ],
      [
        {
          shape_key: "p3-grid",
          shape_type: "hundred_grid",
          data: { rows: 2, cols: 2, filled: 3 },
          layout: { area: "right" },
        },
      ],
    ),
    bodyPage(
      4,
      "concept",
      "抽象分子分母的含义",
      "把披萨、彩纸、量杯三个情境并列的简洁插画",
      [
        { key: "p4-title", role: "title", text: "分数各部分的名称" },
        { key: "p4-body", role: "body", text: "分母表示平均分的份数，分子表示取出的份数。" },
      ],
      [
        {
          shape_key: "p4-formula",
          shape_type: "formula",
          data: { latex: "\\frac{3}{4}", annotation: { numerator: "取的份数", denominator: "平均分的份数" } },
          layout: { area: "center" },
        },
      ],
    ),
    bodyPage(
      5,
      "practice",
      "分层练习巩固读写",
      "三组不同平均分方式的涂色图形练习卡",
      [
        { key: "p5-title", role: "title", text: "练一练" },
        { key: "p5-q", role: "question", text: "用分数表示每幅图中的涂色部分。" },
        { key: "p5-a", role: "answer", text: "①2/3 ②3/5 ③5/8" },
      ],
      [
        {
          shape_key: "p5-bar",
          shape_type: "ratio_bar",
          data: { total: 5, filled: 3 },
          layout: { area: "bottom" },
        },
      ],
    ),
    bodyPage(
      6,
      "summary",
      "回顾本课核心结论",
      "板书风格的知识结构简图与纸艺元素点缀",
      [
        { key: "p6-title", role: "title", text: "今天我们学会了" },
        { key: "p6-body", role: "body", text: "把一个整体平均分成若干份，取其中的几份，就用几分之几表示。" },
      ],
    ),
  ];
}

export function buildShots(): VideoShot[] {
  return [
    {
      shot_id: "SHOT-01",
      scene_id: "SCENE-01",
      position: 1,
      duration_seconds: 10,
      visible_beat: "夜晚树洞前，松鼠把整块巧克力平均掰成四块收进木盒",
      start_state: "松鼠捧着完整巧克力站在树洞口，月光照亮洞口",
      end_state: "木盒里四块巧克力摆放整齐，松鼠满意合上盒盖",
      camera: {
        framing: "中景",
        angle: "平视",
        movement: "缓慢推近",
        start_composition: "松鼠居中，树洞在右后景",
        end_composition: "木盒特写占画面下三分之一",
      },
      action: "松鼠把巧克力沿刻痕平均掰成四块，逐块放进木盒并数数",
      asset_usages: [
        { image_index: 1, asset_version_id: uuid(1601), semantic_name: "松鼠守卫", purpose: "主体角色一致性" },
        { image_index: 2, asset_version_id: uuid(1602), semantic_name: "树洞夜景", purpose: "场景空镜" },
        { image_index: 3, asset_version_id: uuid(1603), semantic_name: "四格巧克力", purpose: "关键道具" },
      ],
      prompt_text:
        "参考[图1]松鼠角色、[图2]树洞夜景与[图3]四格巧克力：夜晚月光下，松鼠在树洞口把一整块巧克力沿刻痕平均掰成四块并放入木盒，镜头缓慢推近至木盒特写。手工毛毡质感，温暖月光，无文字。",
      narration_text: "松鼠守卫把最珍贵的巧克力平均分成了四块，藏进树洞。",
      dialogue_text: "",
      sound_intent: "夜晚虫鸣与轻快的木质音效",
      continuity_notes: "巧克力四块等大；木盒样式与后续镜头一致",
      negative_constraints: ["文字", "水印", "恐怖气氛"],
    },
    {
      shot_id: "SHOT-02",
      scene_id: "SCENE-02",
      position: 2,
      duration_seconds: 10,
      visible_beat: "清晨松鼠打开木盒，发现只剩一块巧克力，地上留有可疑爪印",
      start_state: "晨光中木盒关闭，松鼠伸爪开盒",
      end_state: "盒内仅剩一块巧克力，松鼠瞪大眼睛，地面爪印清晰",
      camera: {
        framing: "近景",
        angle: "俯视过渡到平视",
        movement: "一次缓慢摇移",
        start_composition: "木盒盖特写",
        end_composition: "松鼠惊讶表情与爪印同框",
      },
      action: "开盒、愣住、低头发现爪印",
      asset_usages: [
        { image_index: 1, asset_version_id: uuid(1601), semantic_name: "松鼠守卫", purpose: "主体角色一致性" },
        { image_index: 2, asset_version_id: uuid(1603), semantic_name: "四格巧克力", purpose: "道具连续性（仅剩一块）" },
      ],
      prompt_text:
        "参考[图1]松鼠角色与[图2]巧克力道具：清晨树洞里，松鼠打开木盒发现四块巧克力只剩一块，地面有可疑爪印，镜头从盒盖俯视缓慢摇至松鼠惊讶表情。毛毡质感，晨光，无文字。",
      narration_text: "第二天清晨，盒子里只剩下一块！",
      dialogue_text: "",
      sound_intent: "悬疑音效渐入",
      continuity_notes: "剩余一块的位置与 SHOT-01 摆放一致；爪印样式与 SHOT-03 相同",
      negative_constraints: ["文字", "血腥", "夸张恐怖"],
    },
    {
      shot_id: "SHOT-03",
      scene_id: "SCENE-03",
      position: 3,
      duration_seconds: 15,
      visible_beat: "松鼠警长在案情板前比对爪印，写下「失窃：？」的问号",
      start_state: "案情板贴着巧克力照片与爪印素描",
      end_state: "粉笔停在「失窃：」后的空白处，问号闪烁定格",
      camera: {
        framing: "中近景",
        angle: "平视",
        movement: "固定机位微推",
        start_composition: "案情板占画面三分之二",
        end_composition: "粉笔与空白处特写",
      },
      action: "警长踱步、指点案情板、举粉笔欲写又停",
      asset_usages: [
        { image_index: 1, asset_version_id: uuid(1601), semantic_name: "松鼠守卫", purpose: "主体角色（戴警长帽变体说明）" },
        { image_index: 2, asset_version_id: uuid(1604), semantic_name: "案情板", purpose: "关键道具" },
      ],
      prompt_text:
        "参考[图1]松鼠角色与[图2]案情板道具：松鼠警长在案情板前分析巧克力失窃案，粉笔写到「失窃：」后停住，画面定格在空白与问号。毛毡质感，台灯暖光，无可读文字（板面文字用抽象线条示意）。",
      narration_text: "被偷走的巧克力，到底占整块的多少？松鼠警长需要一个准确的说法。",
      dialogue_text: "",
      sound_intent: "悬念收束，留白",
      continuity_notes: "结尾必须停在提问瞬间（交接时刻），不得出现任何分数写法",
      negative_constraints: ["分数符号", "数字", "文字", "答案提示"],
    },
  ];
}

export const promptFixtures: Record<string, { editable: string; locked: { title: string; summary: string }[]; context: { title: string; detail: string }[] }> = {
  lesson_plan: {
    editable:
      "请为三年级上册「认识几分之几」设计一份完整教案。以动手操作为主线：折一折、涂一涂、说一说；重点建立「平均分的份数—取的份数」对应关系；练习分层设计；课堂总结引导学生用自己的话概括。",
    locked: [
      { title: "内容结构", summary: "按当前内容定义（默认十二部分）输出结构化教案" },
      { title: "安全与年龄", summary: "面向 8-9 岁学生，禁止超纲概念与不当内容" },
    ],
    context: [
      { title: "教材范围", detail: "认识几分之几（教材第 90-93 页，已确认范围）" },
      { title: "课时定位", detail: "第 2 课时：认识几分之几（40 分钟）" },
    ],
  },
  intro_options: {
    editable:
      "为本课时生成三类九套课堂导入创意：科普、应用、故事各三套。每套先给出完全独立于课程的创意核心与钩子，再补充唯一课程锚点、课堂首问、交接时刻与不得提前讲授内容，并给出推荐度评分。",
    locked: [
      { title: "两阶段隔离", summary: "独立创意阶段不读取教材与教案；锚定阶段只补充最小回接" },
      { title: "质量门", summary: "九套实质不同；最高推荐分唯一；不得提前讲授" },
    ],
    context: [{ title: "课时范围", detail: "认识几分之几（已批准课时划分）" }],
  },
  ppt_outline: {
    editable:
      "基于已批准教案生成 PPT 大纲：每页一个唯一教学任务，覆盖导入、探究、概念建构、练习与总结；保留教材知识顺序；标注每页来源与页型。",
    locked: [
      { title: "页级合同", summary: "每页输出四层结构（画布/主视觉/可编辑内容/排版）" },
      { title: "白底规则", summary: "正文页背景固定纯白，文字公式保持可编辑" },
    ],
    context: [{ title: "上游", detail: "已批准教案 v2" }],
  },
  ppt_cover: {
    editable:
      "为「认识几分之几」设计 3 张封面候选：表达平均分与取几份的核心意象（如四分之三披萨），手工纸艺质感，构图留白，适合投影。画面中不出现任何文字与数字。",
    locked: [
      { title: "视觉合同", summary: "采用后锁定整套视觉语言；正文继承风格但保持白底" },
      { title: "禁止项", summary: "文字、数字、公式不得烘焙进图片" },
    ],
    context: [{ title: "上游", detail: "已批准 PPT 大纲 v1" }],
  },
  ppt_body: {
    editable:
      "按页级设计批量生成正文页：每页一个图片主视觉 + 可编辑文字与数学图形；背景纯白；插画继承封面视觉语言。",
    locked: [
      { title: "白底规则", summary: "正文页 background_mode=solid_white #FFFFFF" },
      { title: "可编辑合同", summary: "标题、题面、数字、公式使用可编辑元素" },
    ],
    context: [
      { title: "视觉风格", detail: "封面视觉合同 v1（纸艺质感 / 暖光 / 山海蓝点缀）" },
      { title: "页面清单", detail: "6 页（1 封面 + 5 正文）" },
    ],
  },
  ppt_export: {
    editable: "将当前已批准页面装配为可编辑 PPTX：底层白底画布、中层图片资产、上层可编辑文字与数学图形，同时输出 PDF 预览。",
    locked: [{ title: "装配规则", summary: "混合结构装配，关键内容保持可编辑" }],
    context: [{ title: "页面", detail: "6 页全部批准" }],
  },
  video_script: {
    editable:
      "把选定导入方案「巧克力守卫战」发展为完整母版剧本：三场结构（藏宝—失窃—立案），结尾停在警长写下问号的交接时刻；包含场次、画面动作、旁白与声音意图；不出现任何分数写法。",
    locked: [
      { title: "输入边界", summary: "只读取选定方案快照，不读取教案与教材" },
      { title: "交接时刻", summary: "结尾必须停在 handoff_moment，不得讲出保留内容" },
    ],
    context: [{ title: "选定方案", detail: "INTRO-STO-01 巧克力守卫战（故事 / 88 分）" }],
  },
  video_storyboard: {
    editable: "将母版剧本拆为粗分镜：按故事节拍列出每段发生什么、可见变化、预计时长与资产需求；不写模型提示词。",
    locked: [{ title: "粗分镜边界", summary: "只描述节拍与资产需求，不含供应商提示词" }],
    context: [{ title: "上游", detail: "已批准母版剧本 v1" }],
  },
  video_style: {
    editable:
      "为本视频提出视觉母图候选：手工毛毡质感、暖色月光、圆润造型、低饱和背景；锁定角色与场景的材质、光线与配色语言。",
    locked: [{ title: "风格合同", summary: "采用后锁定 video_style_contract，约束后续图片与视频" }],
    context: [{ title: "上游", detail: "已批准粗分镜 v1" }],
  },
  video_assets: {
    editable: "按资产清单生成四类图片：松鼠守卫（角色）、树洞夜景（场景）、四格巧克力（道具）、案情板（道具）；全部继承视觉母图风格。",
    locked: [
      { title: "资产登记", summary: "人物/场景/道具/生物分别登记，场景默认无人物" },
      { title: "风格约束", summary: "严格执行 video_style_contract" },
    ],
    context: [{ title: "清单", detail: "4 项资产（1 角色 / 1 场景 / 2 道具）" }],
  },
  video_clips: {
    editable: "按细分镜为每个镜头生成候选视频：严格使用已批准垫图，保持角色、道具与光线连续；无对白画面，声音后期合成。",
    locked: [
      { title: "镜头合同", summary: "一个镜头一个节拍一个主运镜；10/15 秒规格" },
      { title: "候选规则", summary: "候选保存到项目后才成为正式片段" },
    ],
    context: [{ title: "镜头", detail: "3 个镜头（10s/10s/15s）" }],
  },
  video_compose: {
    editable: "按镜头顺序合成完整视频：拼接当前正式片段，混入旁白、音效与字幕，输出 MP4 与质量报告。",
    locked: [{ title: "合成规则", summary: "只读取每个镜头当前正式片段与已批准音频" }],
    context: [{ title: "时间线", detail: "3 个正式片段 + 旁白 3 段 + 字幕" }],
  },
};
