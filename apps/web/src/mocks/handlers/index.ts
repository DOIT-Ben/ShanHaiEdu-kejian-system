import { authHandlers } from "./auth";
import { homeHandlers } from "./home";
import { projectHandlers } from "./projects";
import { lessonHandlers } from "./lessons";
import { runHandlers } from "./runs";
import { artifactHandlers } from "./artifacts";
import { assetHandlers } from "./assets";
import { taskHandlers } from "./tasks";
import { deliveryHandlers } from "./delivery";
import { adminHandlers } from "./admin";
import { eventStreamHandlers } from "./events";

export const handlers = [
  ...authHandlers,
  ...homeHandlers,
  ...projectHandlers,
  ...lessonHandlers,
  ...runHandlers,
  ...artifactHandlers,
  ...assetHandlers,
  ...taskHandlers,
  ...deliveryHandlers,
  ...adminHandlers,
  ...eventStreamHandlers,
];
