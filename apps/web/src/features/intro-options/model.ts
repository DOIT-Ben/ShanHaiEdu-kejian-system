export type IntroCategory = "science" | "application" | "story";

export type IntroOption = {
  key: string;
  category: IntroCategory;
  title: string;
  score: number;
  concept: string;
  hook: string;
  medium: string;
  duration: number;
  courseAnchor: string;
  firstQuestion: string;
  handoff: string;
  mustNotPreteach: string[];
  reason: string;
};
