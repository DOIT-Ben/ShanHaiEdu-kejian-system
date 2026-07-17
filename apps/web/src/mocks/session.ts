/**
 * Mock 会话持久化：模拟 shanhai_session Cookie 的「刷新仍在登录态」行为。
 * 仅存用户 id（演示数据，无敏感信息）；关闭标签页即失效，贴近会话 Cookie。
 */
const KEY = "sh-mock-session";

export function persistMockSession(userId: string | null): void {
  try {
    if (userId) window.sessionStorage.setItem(KEY, userId);
    else window.sessionStorage.removeItem(KEY);
  } catch {
    // 隐私模式等场景下不可用时静默降级为内存会话
  }
}

export function restoreMockSession(): string | null {
  try {
    return window.sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}
