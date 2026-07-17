import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/** Vitest 用 Node MSW 服务器；测试内通过 seedDb/applyScenario 控制世界。 */
export const server = setupServer(...handlers);
