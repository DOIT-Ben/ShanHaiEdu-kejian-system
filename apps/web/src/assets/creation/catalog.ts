import imageFractionMarket from "./images/image-fraction-market.webp";
import imageGeometryGarden from "./images/image-geometry-garden.webp";
import imageJuiceObservation from "./images/image-juice-observation.webp";
import pptContentClassDiscussion from "./ppt/ppt-content-class-discussion.webp";
import pptContentHundredGrid from "./ppt/ppt-content-hundred-grid.webp";
import pptContentMarketLabels from "./ppt/ppt-content-market-labels.webp";
import pptCoverClassroomDiscovery from "./ppt/ppt-cover-classroom-discovery.webp";
import pptCoverGridWindow from "./ppt/ppt-cover-grid-window.webp";
import pptCoverJuiceLabel from "./ppt/ppt-cover-juice-label.webp";
import videoShot01Classroom from "./video/video-shot-01-classroom.webp";
import videoShot02LabelCloseup from "./video/video-shot-02-label-closeup.webp";
import videoShot03StudentDiscovery from "./video/video-shot-03-student-discovery.webp";
import videoShot04QuestionFrame from "./video/video-shot-04-question-frame.webp";

export type CreationVisualAsset = Readonly<{
  alt: string;
  focalPoint?: `${number}% ${number}%`;
  naturalHeight: number;
  naturalWidth: number;
  src: string;
}>;

export const creationImageAssetCatalog = [
  {
    alt: "三瓶彩色饮品和几何卡片组成的课堂观察场景",
    focalPoint: "50% 52%",
    naturalHeight: 1086,
    naturalWidth: 1448,
    src: imageJuiceObservation,
  },
  {
    alt: "老师和两名学生在水果分份教具前进行课堂观察",
    focalPoint: "50% 54%",
    naturalHeight: 1086,
    naturalWidth: 1448,
    src: imageFractionMarket,
  },
  {
    alt: "老师和两名学生用几何图形搭建课堂作品",
    focalPoint: "50% 48%",
    naturalHeight: 1086,
    naturalWidth: 1448,
    src: imageGeometryGarden,
  },
] as const satisfies readonly CreationVisualAsset[];

export const creationPptCoverAssetCatalog = [
  {
    alt: "百格光窗与果汁标签组成的百分数课件封面",
    naturalHeight: 941,
    naturalWidth: 1672,
    src: pptCoverGridWindow,
  },
  {
    alt: "暖光桌面上的三瓶果汁组成的百分数课件封面",
    naturalHeight: 941,
    naturalWidth: 1672,
    src: pptCoverJuiceLabel,
  },
  {
    alt: "师生围绕果汁标签讨论的百分数课件封面",
    naturalHeight: 941,
    naturalWidth: 1672,
    src: pptCoverClassroomDiscovery,
  },
] as const satisfies readonly CreationVisualAsset[];

export const creationPptContentAssetCatalog = [
  {
    alt: "学生观察三瓶果汁标签的课堂情境图",
    naturalHeight: 1086,
    naturalWidth: 1448,
    src: pptContentMarketLabels,
  },
  {
    alt: "百格图中涂出百分之三十七的课堂示意图",
    naturalHeight: 1086,
    naturalWidth: 1448,
    src: pptContentHundredGrid,
  },
  {
    alt: "学生在黑板前交流百分数判断理由的课堂图",
    naturalHeight: 1086,
    naturalWidth: 1448,
    src: pptContentClassDiscussion,
  },
] as const satisfies readonly CreationVisualAsset[];

export const creationVideoShotAssetCatalog = [
  {
    alt: "老师带领两名学生观察数学材料的温暖课堂",
    focalPoint: "50% 45%",
    naturalHeight: 941,
    naturalWidth: 1672,
    src: videoShot01Classroom,
  },
  {
    alt: "两名学生近距离观察三瓶果汁标签",
    naturalHeight: 941,
    naturalWidth: 1672,
    src: videoShot02LabelCloseup,
  },
  {
    alt: "学生举手分享观察果汁标签后的发现",
    naturalHeight: 941,
    naturalWidth: 1672,
    src: videoShot03StudentDiscovery,
  },
  {
    alt: "课堂画面停在等待学生回答的首问",
    naturalHeight: 941,
    naturalWidth: 1672,
    src: videoShot04QuestionFrame,
  },
] as const satisfies readonly CreationVisualAsset[];

export const creationImageAssets = [
  creationImageAssetCatalog[0].src,
  creationImageAssetCatalog[1].src,
  creationImageAssetCatalog[2].src,
] as const;

export const creationPptCoverAssets = [
  creationPptCoverAssetCatalog[0].src,
  creationPptCoverAssetCatalog[1].src,
  creationPptCoverAssetCatalog[2].src,
] as const;

export const creationPptContentAssets = [
  creationPptContentAssetCatalog[0].src,
  creationPptContentAssetCatalog[1].src,
  creationPptContentAssetCatalog[2].src,
] as const;

export const creationVideoShotAssets = [
  creationVideoShotAssetCatalog[0].src,
  creationVideoShotAssetCatalog[1].src,
  creationVideoShotAssetCatalog[2].src,
  creationVideoShotAssetCatalog[3].src,
] as const;

function atVariant<T>(items: readonly T[], variant: number) {
  const index = ((variant % items.length) + items.length) % items.length;
  return items[index] as T;
}

export function getCreationImageAsset(variant: number): CreationVisualAsset {
  return atVariant(creationImageAssetCatalog, variant);
}

export function getCreationVideoShotAsset(variant: number): CreationVisualAsset {
  return atVariant(creationVideoShotAssetCatalog, variant);
}
