import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/** Node 端（Vitest）MSW server；测试 setup 中启动。 */
export const server = setupServer(...handlers);
