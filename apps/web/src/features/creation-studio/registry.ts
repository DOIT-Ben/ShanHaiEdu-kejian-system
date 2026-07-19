import { Image, PlaySquare, Presentation } from "lucide-react";
import type { StudioConfig, StudioType } from "@/features/creation-studio/model";

export const studioRegistry: Record<StudioType, StudioConfig> = {
  image: {
    type: "image",
    path: "images",
    title: "图片创作台",
    entryTitle: "画一张教学图片",
    description: "制作教学情境、教具、角色、场景和数学关系图。",
    primaryLabel: "开始创作图片",
    icon: Image,
  },
  video: {
    type: "video",
    path: "videos",
    title: "视频创作台",
    entryTitle: "做一段课堂视频",
    description: "用参考画面说明怎样变化，一次得到多段可比较的视频。",
    primaryLabel: "开始创作视频",
    icon: PlaySquare,
  },
  presentation: {
    type: "presentation",
    path: "presentations",
    title: "PPT 创作台",
    entryTitle: "制作一套教学 PPT",
    description: "从内容到白底图片化课堂课件，保留关键内容可编辑。",
    primaryLabel: "开始制作 PPT",
    icon: Presentation,
  },
};
