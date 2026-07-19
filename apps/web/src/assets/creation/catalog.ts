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

export const creationImageAssets = [
  imageJuiceObservation,
  imageFractionMarket,
  imageGeometryGarden,
] as const;

export const creationPptCoverAssets = [
  pptCoverGridWindow,
  pptCoverJuiceLabel,
  pptCoverClassroomDiscovery,
] as const;

export const creationPptContentAssets = [
  pptContentMarketLabels,
  pptContentHundredGrid,
  pptContentClassDiscussion,
] as const;

export const creationVideoShotAssets = [
  videoShot01Classroom,
  videoShot02LabelCloseup,
  videoShot03StudentDiscovery,
  videoShot04QuestionFrame,
] as const;
