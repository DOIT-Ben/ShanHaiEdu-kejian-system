import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Select } from "@/shared/ui/Select";

const options = [
  { label: "六年级", value: "grade-6" },
  { label: "五年级", value: "grade-5" },
  { label: "四年级", value: "grade-4" },
];

const meta = {
  component: Select,
  title: "基础组件/Select",
  args: {
    ariaLabel: "选择年级",
    onValueChange: () => undefined,
    options,
    value: "grade-6",
  },
} satisfies Meta<typeof Select>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Standard: Story = {};

export const CompactWithLabel: Story = {
  args: {
    leadingLabel: "比例",
    options: [
      { label: "16:9", value: "16:9" },
      { label: "4:3", value: "4:3" },
      { label: "1:1", value: "1:1" },
    ],
    size: "sm",
    value: "16:9",
  },
};

export function Interactive() {
  const [value, setValue] = useState("grade-6");
  return (
    <Select
      ariaLabel="选择年级"
      className="w-56"
      onValueChange={setValue}
      options={options}
      value={value}
    />
  );
}
