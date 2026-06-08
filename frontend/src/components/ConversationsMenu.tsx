import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquarePlus, MessagesSquare, Check, ChevronDown } from "lucide-react";
import { listConversations, type Conversation } from "../conversationsApi";
import { startNewConversation, resumeConversation } from "../chatStore";
import { cn } from "@/lib/utils";

/**
 * ConversationsMenu — per-agent multi-conversation control (V2 convos-first). A small dropdown in
 * the AgentWindow header: lists this agent's past conversations (active one marked), a "New
 * conversation" button, and resumes a conversation on click (loads its transcript into the window).
 * Used by Main (ceo), Specialist (the chosen agent), and every Group window — all via AgentWindow.
 */
function fmtWhen(iso: string | null): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function ConversationsMenu({ alias }: { alias: string }) {
  const [open, setOpen] = useState(false);
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      setConvos(await listConversations(alias));
    } catch {
      setConvos([]);
    }
  }, [alias]);

  // close on outside click
  useEffect(() => {
    if (!open) return;
    refresh();
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open, refresh]);

  const onNew = async () => {
    setBusy(true);
    await startNewConversation(alias);
    await refresh();
    setBusy(false);
    setOpen(false);
  };

  const onPick = async (c: Conversation) => {
    if (c.active) {
      setOpen(false);
      return;
    }
    setBusy(true);
    await resumeConversation(alias, c);
    await refresh();
    setBusy(false);
    setOpen(false);
  };

  const activeTitle = convos.find((c) => c.active)?.title;

  return (
    <div ref={ref} className="convos-menu relative">
      <button
        type="button"
        className="convos-toggle"
        title="Conversations — browse, resume, or start a new one"
        onClick={() => setOpen((o) => !o)}
      >
        <MessagesSquare size={13} />
        <span className="convos-toggle-label">{activeTitle ? activeTitle : "Conversation"}</span>
        <ChevronDown size={13} />
      </button>

      {open && (
        <div className="convos-panel" role="menu">
          <button className="convos-new" onClick={onNew} disabled={busy}>
            <MessageSquarePlus size={14} /> New conversation
          </button>
          <div className="convos-list">
            {convos.length === 0 ? (
              <div className="convos-empty">No conversations yet</div>
            ) : (
              convos.map((c) => (
                <button
                  key={c.id}
                  className={cn("convos-item", c.active && "convos-item-active")}
                  onClick={() => onPick(c)}
                  disabled={busy}
                  title={c.session_id ?? "new (no turns yet)"}
                >
                  <span className="convos-item-check">{c.active ? <Check size={13} /> : null}</span>
                  <span className="convos-item-title">{c.title || "Untitled conversation"}</span>
                  <span className="convos-item-when">{fmtWhen(c.last_active)}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
