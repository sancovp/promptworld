// agentBus — a tiny in-process pub/sub that DEMULTIPLEXES the single /ws connection by
// alias. App opens ONE WebSocket and publishes each {alias, event} to subscribers for that
// alias; each AgentWindow subscribes to its own alias. This keeps one socket but N windows.

type Handler = (event: any) => void;

const subscribers: Record<string, Set<Handler>> = {};

export function subscribe(alias: string, handler: Handler): () => void {
  (subscribers[alias] ??= new Set()).add(handler);
  return () => {
    subscribers[alias]?.delete(handler);
  };
}

export function publish(alias: string, event: any): void {
  const set = subscribers[alias];
  if (!set) return;
  for (const h of set) {
    try {
      h(event);
    } catch {
      /* a handler error must never break the stream */
    }
  }
}
