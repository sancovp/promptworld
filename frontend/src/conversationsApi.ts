/**
 * conversationsApi — the per-agent MULTI-conversation backend (V2 convos-first).
 *
 * Each agent alias owns a LIST of conversations + an ACTIVE pointer. The active one is what
 * /api/chat + /api/gym roll forward. These helpers let the UI browse past conversations, start a
 * New one, resume an old one, and load a conversation's transcript. Mirrors server/promptworld_
 * server.py _register_conversation_routes.
 */
import type { ThreadMessageLike } from "@assistant-ui/react";

export interface Conversation {
  id: string; // STABLE handle (uuid)
  session_id: string | null; // the SDK session id (null until the convo's first turn runs)
  started_at: string | null;
  last_active: string | null;
  title: string | null;
  active: boolean;
}

async function jsonOrThrow(r: Response) {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

/** All conversations for an agent (newest first; the active one tagged `active:true`). */
export async function listConversations(alias: string): Promise<Conversation[]> {
  const r = await fetch(`/api/conversations/${encodeURIComponent(alias)}`);
  const d = await jsonOrThrow(r);
  return (d.conversations ?? []) as Conversation[];
}

/** Open a FRESH conversation (becomes active; the old one stays browsable). */
export async function newConversation(alias: string): Promise<Conversation> {
  const r = await fetch(`/api/conversations/${encodeURIComponent(alias)}/new`, { method: "POST" });
  const d = await jsonOrThrow(r);
  return d.conversation as Conversation;
}

/** Make a conversation active (resume it). `handle` = its id OR its session_id. */
export async function setActiveConversation(alias: string, handle: string): Promise<Conversation> {
  const r = await fetch(`/api/conversations/${encodeURIComponent(alias)}/active`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ session_id: handle }),
  });
  const d = await jsonOrThrow(r);
  return d.active as Conversation;
}

/** A past conversation's transcript as assistant-ui messages (empty for a never-run convo). */
export async function getTranscript(alias: string, sessionId: string): Promise<ThreadMessageLike[]> {
  const r = await fetch(
    `/api/conversations/${encodeURIComponent(alias)}/${encodeURIComponent(sessionId)}`,
  );
  const d = await jsonOrThrow(r);
  return (d.messages ?? []) as ThreadMessageLike[];
}
