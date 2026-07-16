import type { StreamEvent } from "@/shared/api/eventStream";
import { getDb, nextId, nowIso } from "./db";

/**
 * Mock 事件广播：SSE handler 订阅；事件同时进入回放缓冲，
 * 支持 Last-Event-ID 断点续传。
 */
type Subscriber = (event: StreamEvent) => void;

const subscribers = new Set<Subscriber>();
const EVENT_BUFFER_LIMIT = 500;

export function publishEvent(
  input: Omit<StreamEvent, "event_id" | "occurred_at"> & { occurred_at?: string },
): StreamEvent {
  const db = getDb();
  const event: StreamEvent = {
    ...input,
    event_id: nextId(db, "evt"),
    occurred_at: input.occurred_at ?? nowIso(),
    payload: input.payload ?? {},
  };
  db.events.push(event);
  if (db.events.length > EVENT_BUFFER_LIMIT) {
    db.events.splice(0, db.events.length - EVENT_BUFFER_LIMIT);
  }
  for (const subscriber of subscribers) subscriber(event);
  return event;
}

export function subscribeEvents(subscriber: Subscriber): () => void {
  subscribers.add(subscriber);
  return () => subscribers.delete(subscriber);
}

export function eventsAfter(lastEventId: string | null): StreamEvent[] {
  const db = getDb();
  if (!lastEventId) return [];
  const index = db.events.findIndex((e) => e.event_id === lastEventId);
  if (index === -1) return [];
  return db.events.slice(index + 1);
}

export function clearSubscribers(): void {
  subscribers.clear();
}
