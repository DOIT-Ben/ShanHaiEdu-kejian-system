import type { Meta, StoryObj } from "@storybook/react-vite";
import { Image } from "lucide-react";
import { type ComponentProps, useState } from "react";
import { CreationComposer } from "@/features/creation-studio/CreationComposer";
import type { CreationSettings } from "@/features/creation-studio/model";

const settings: CreationSettings = {
  candidateCount: "3",
  duration: "8",
  model: "balanced",
  ratio: "1:1",
  referenceName: "",
  style: "illustration",
};

function EditableStory(args: ComponentProps<typeof CreationComposer>) {
  const [description, setDescription] = useState(args.description);
  const [currentSettings, setCurrentSettings] = useState(args.settings);
  return (
    <CreationComposer
      {...args}
      description={description}
      onDescriptionChange={setDescription}
      onSettingsChange={(patch) => setCurrentSettings((value) => ({ ...value, ...patch }))}
      settings={currentSettings}
    />
  );
}

const meta = {
  title: "创作台/输入区",
  component: CreationComposer,
  tags: ["core-viewport"],
  parameters: { layout: "fullscreen" },
  args: {
    advancedOpen: false,
    advancedPanel: <p className="text-sm">画面细节面板</p>,
    config: {
      description: "输入创作要求并生成课堂插画",
      entryTitle: "课堂插画",
      icon: Image,
      path: "/app/creation/images",
      primaryLabel: "生成图片",
      title: "图片创作台",
      type: "image",
    },
    description: "把百分数放进水果摊标签里，用清透插画表现课堂观察。",
    descriptionLabel: "描述你想生成的画面",
    onAdvancedOpenChange: () => undefined,
    onDescriptionChange: () => undefined,
    onGenerate: () => undefined,
    onPromptReview: () => undefined,
    onSettingsChange: () => undefined,
    settings,
    stage: "draft",
    type: "image",
  },
} satisfies Meta<typeof CreationComposer>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Draft: Story = {};
export const Generating: Story = { args: { stage: "running" } };
export const WithAdvancedPanel: Story = { args: { advancedOpen: true } };

export const Editable: Story = {
  render: (args) => <EditableStory {...args} />,
};
