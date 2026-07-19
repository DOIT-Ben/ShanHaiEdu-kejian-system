import type { ContentData, ContentDefinition } from "@/features/content-definition/model";

export const lessonPlanDefinition: ContentDefinition = {
  definition_key: "primary_math.lesson_plan",
  title: "小学数学教案",
  description: "当前项目固定使用此内容结构版本",
  fields: [
    {
      field_key: "teaching_content",
      label: "教学内容",
      type: "rich_text",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "textbook_analysis",
      label: "教材分析",
      type: "rich_text",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "student_analysis",
      label: "学情分析",
      type: "rich_text",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "design_intent",
      label: "设计意图",
      type: "rich_text",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "objectives",
      label: "教学目标",
      type: "list",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "key_points",
      label: "教学重难点及突破策略",
      type: "rich_text",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "preparation",
      label: "教学准备",
      type: "list",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "process",
      label: "教学过程",
      type: "timeline",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "board_design",
      label: "板书设计",
      type: "rich_text",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "summary",
      label: "课堂总结",
      type: "rich_text",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "homework",
      label: "分层作业",
      type: "list",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "reflection",
      label: "教学反思",
      type: "rich_text",
      required: false,
      editable: true,
      deletable: false,
    },
  ],
};

export const lessonPlanData: ContentData = {
  teaching_content:
    "理解百分数表示一个数是另一个数的百分之几，能够正确读写百分数，并在真实信息中解释百分数的含义。",
  textbook_analysis: "教材从生活中的百分数信息出发，让学生在比较和表达中体会百分数是特殊的比率。",
  student_analysis: "学生已掌握分数意义和小数读写，但容易把百分数误认为带百分号的普通分数。",
  design_intent: "以可见的百格图和生活数据建立整体与部分的联系，再让学生自主概括百分数的意义。",
  objectives: ["能结合具体情境解释百分数的意义", "能正确读写百分数", "感受百分数便于比较的价值"],
  key_points:
    "重点是从数量关系理解百分数；难点是区分百分数与表示具体数量的分数。通过百格图、同类数据比较和反例辨析突破。",
  preparation: ["百格图学具", "生活中的百分数标签", "可编辑课堂课件"],
  process: [
    "观察信息：找出生活中的百分数",
    "动手表示：在百格图中表示 37%",
    "比较概括：说清楚整体、部分与百分数",
    "辨析应用：判断哪些分数可以写成百分数",
  ],
  board_design: "百分数\n表示一个数是另一个数的百分之几\n37% 读作：百分之三十七",
  summary: "学生用自己的话说明百分数的意义，并举出一个生活实例。",
  homework: ["基础：完成教材对应练习", "提高：收集三个生活中的百分数并解释含义"],
  reflection: "课后根据学生对整体‘1’的理解情况补充记录。",
};

export function createLessonPlanData(knowledgePoint: string, scope = "") {
  const topic = knowledgePoint.trim() || "本课知识点";
  const lessonScope = scope.trim() || `围绕${topic}完成概念理解、例题探究与课堂练习。`;
  return {
    teaching_content: `${lessonScope} 学生将在具体情境中理解${topic}的核心关系，并尝试用自己的话表达。`,
    textbook_analysis: `教材围绕${topic}安排情境、例题和练习，引导学生从观察信息逐步建立清晰的数量关系。`,
    student_analysis: `学生已经积累与${topic}相关的生活经验，但需要借助图示、操作和同伴交流把直观发现说清楚。`,
    design_intent: `从${topic}的真实情境出发，先让学生发现问题，再通过比较、表达和验证形成可迁移的理解。`,
    objectives: [
      `能用自己的话说明${topic}的核心含义`,
      `能结合教材情境完成${topic}相关的观察和表达`,
      `能在练习中检查自己的判断并解释理由`,
    ],
    key_points: `重点是理解${topic}背后的数量关系；难点是把直观观察转化为准确表达。通过图示、操作和反例辨析逐步突破。`,
    preparation: ["教材中的相关图片或实物", "可编辑课堂课件", "课堂练习材料"],
    process: [
      `情境观察：找出与${topic}有关的信息`,
      "动手表示：用图示或操作说明自己的发现",
      `交流概括：说清${topic}的核心关系`,
      "辨析应用：用一个新情境检验理解",
    ],
    board_design: `${topic}\n核心关系：先观察，再表达，再验证`,
    summary: `学生用自己的话说清${topic}，并能在新情境中解释判断依据。`,
    homework: [`基础：完成教材中${topic}对应练习`, "拓展：寻找一个生活情境并写下自己的解释"],
    reflection: `课后记录学生对${topic}的理解证据，以及下一次需要补充的示例。`,
  } satisfies ContentData;
}
