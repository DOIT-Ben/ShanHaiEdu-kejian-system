import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";
import { seedDb } from "./seed";
import { applyScenario } from "./scenarios";
import { db } from "./db";
import { ID } from "./ids";
import { restoreMockSession, persistMockSession } from "./session";

/**
 * 浏览器 MSW 启动（仅 mock 模式；main.tsx 用编译期常量守卫，
 * 生产构建中本模块不会被打包）。
 * URL 参数：?scenario=xxx 切场景；?login=demo 预登录教师账号。
 */
export async function startMockWorker(): Promise<void> {
  seedDb();
  const params = new URLSearchParams(window.location.search);
  const scenario = params.get("scenario");
  if (scenario) applyScenario(scenario);
  if (params.get("login") === "demo" || scenario) {
    if (!db.sessionUserId) db.sessionUserId = ID.userTeacher;
    persistMockSession(db.sessionUserId);
  }
  // 刷新恢复：模拟会话 Cookie（存在且用户有效才恢复）
  if (!db.sessionUserId) {
    const restored = restoreMockSession();
    if (restored && db.users.some((u) => u.id === restored)) {
      db.sessionUserId = restored;
    }
  }
  const worker = setupWorker(...handlers);
  await worker.start({
    onUnhandledRequest: (request, print) => {
      const url = new URL(request.url);
      if (url.pathname.startsWith("/api/")) print.warning();
    },
  });
}
