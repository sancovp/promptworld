// editorBus — a tiny in-process pub/sub to request OPENING a file path in the Monaco workbench
// from anywhere in the app (e.g. the profile editor's "Edit prompt (CLAUDE.md)" button). The
// FileExplorer subscribes and opens the path in a tab. On a page with no editor mounted (Group),
// there are no subscribers, so it's a harmless no-op.

type OpenHandler = (path: string) => void;

const handlers = new Set<OpenHandler>();

export function onOpenFile(handler: OpenHandler): () => void {
  handlers.add(handler);
  return () => {
    handlers.delete(handler);
  };
}

export function openFileInEditor(path: string): void {
  for (const h of handlers) {
    try {
      h(path);
    } catch {
      /* a handler error must never break the caller */
    }
  }
}
