import { authHandlers } from "./auth";
import { homeHandlers } from "./home";
import { projectHandlers } from "./projects";
import { nodeRunHandlers } from "./runs";
import { introHandlers } from "./intro";
import { pptHandlers } from "./ppt";
import { videoHandlers } from "./video";
import { creationHandlers } from "./creation";
import { taskHandlers } from "./tasks";
import { adminHandlers } from "./admin";
import { scenarioHandlers } from "../scenarios";

export const handlers = [
  ...scenarioHandlers,
  ...authHandlers,
  ...homeHandlers,
  ...projectHandlers,
  ...nodeRunHandlers,
  ...introHandlers,
  ...pptHandlers,
  ...videoHandlers,
  ...creationHandlers,
  ...taskHandlers,
  ...adminHandlers,
];
