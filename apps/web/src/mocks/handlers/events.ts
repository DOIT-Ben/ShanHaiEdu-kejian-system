import { http, HttpResponse } from "msw";
import type { StreamEvent } from "@/shared/api/eventStream";
import { getDb } from "../db";
import { eventsAfter, subscribeEvents } from "../events";
import { api } from "./http";

function encodeEvent(event: StreamEvent): string {
  return `id: ${event.event_id}\nevent: ${event.event_type}\ndata: ${JSON.stringify(event)}\n\n`;
}

export const eventStreamHandlers = [
  http.get(api("/events"), ({ request }) => {
    const db = getDb();
    if (db.flags.sseAlwaysFail) {
      return new HttpResponse(null, { status: 503 });
    }
    const url = new URL(request.url);
    const lastEventId = url.searchParams.get("last_event_id") ?? request.headers.get("last-event-id");
    const projectId = url.searchParams.get("project_id");

    const encoder = new TextEncoder();
    let cleanup: (() => void) | null = null;

    const stream = new ReadableStream({
      start(controller) {
        let closed = false;
        const safeEnqueue = (text: string) => {
          if (closed) return;
          try {
            controller.enqueue(encoder.encode(text));
          } catch {
            closed = true;
          }
        };
        safeEnqueue(": connected\n\n");
        for (const event of eventsAfter(lastEventId)) {
          if (!projectId || event.project_id === projectId || !event.project_id) {
            safeEnqueue(encodeEvent(event));
          }
        }
        const unsubscribe = subscribeEvents((event) => {
          if (!projectId || event.project_id === projectId || !event.project_id) {
            safeEnqueue(encodeEvent(event));
          }
        });
        const heartbeat = setInterval(() => safeEnqueue(": ping\n\n"), 15_000);
        let dropTimer: ReturnType<typeof setTimeout> | null = null;
        if (db.flags.sseDropAfterMs) {
          dropTimer = setTimeout(() => {
            cleanup?.();
            try {
              controller.close();
            } catch {
              // already closed
            }
          }, db.flags.sseDropAfterMs);
        }
        cleanup = () => {
          closed = true;
          unsubscribe();
          clearInterval(heartbeat);
          if (dropTimer) clearTimeout(dropTimer);
        };
      },
      cancel() {
        cleanup?.();
      },
    });

    return new HttpResponse(stream, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }),
];
