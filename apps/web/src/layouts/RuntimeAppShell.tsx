import { AppShell } from "@/layouts/AppShell";

/**
 * Runtime adapter used by the real API build. Authentication is owned by the
 * server cookie; this shell deliberately does not invent a browser session.
 */
export function RuntimeAppShell() {
  return <AppShell accountInitial="用" accountLabel="当前用户" />;
}
