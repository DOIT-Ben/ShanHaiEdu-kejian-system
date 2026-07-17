import type { Meta, StoryObj } from "@storybook/react";
import { ContentDefinitionRenderer } from "./ContentDefinitionRenderer";
import { parseContentDefinition } from "@/entities/content";

/**
 * 动态教案渲染：结构 100% 来自内容定义数据，换一份定义即换一种教案，
 * 前端零改码（验收 08：两种教案 schema 均可渲染）。
 */

const fivePartDefinition = parseContentDefinition({
  definition_key: "lesson_plan.demo.v1",
  title: "简案结构（演示）",
  sections: [
    {
      key: "objectives",
      title: "教学目标",
      numbering: "chinese",
      required: true,
      fields: [{ key: "items", label: "教学目标", type: "string_list", required: true, min_items: 1 }],
    },
    {
      key: "key_points",
      title: "重点难点",
      numbering: "chinese",
      required: true,
      fields: [{ key: "content", label: "重点难点", type: "rich_text", required: true }],
    },
    {
      key: "process",
      title: "课堂流程",
      numbering: "chinese",
      required: true,
      fields: [
        {
          key: "steps",
          label: "课堂流程",
          type: "repeatable_group",
          required: true,
          min_items: 1,
          item_fields: [
            { key: "name", label: "环节名称", type: "text", required: true },
            { key: "minutes", label: "时长（分钟）", type: "number", required: true },
            { key: "teacher", label: "教师活动", type: "rich_text", required: true },
          ],
        },
      ],
    },
  ],
});

const meta: Meta<typeof ContentDefinitionRenderer> = {
  title: "内容定义/动态教案渲染",
  component: ContentDefinitionRenderer,
};
export default meta;

type Story = StoryObj<typeof ContentDefinitionRenderer>;

export const 可编辑: Story = {
  args: {
    definition: fivePartDefinition,
    value: {
      objectives: { items: ["认识几分之几", "会读写简单分数"] },
      key_points: { content: "理解分子分母与平均分份数的对应关系。" },
      process: { steps: [{ name: "情境导入", minutes: 5, teacher: "播放导入视频，提出问题。" }] },
    },
    readOnly: false,
  },
};

export const 只读带校验提醒: Story = {
  args: {
    ...可编辑.args,
    readOnly: true,
    issues: [
      { key: "w1", severity: "warning", message: "课堂流程仅 1 个环节，建议补充。", field_path: "process.steps" },
    ],
  },
};
