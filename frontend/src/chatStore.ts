/**
 * chatStore — a GLOBAL, per-alias chat-state singleton.
 *
 * WHY: the 3-page layout (Main / Specialist / Group) mounts and UNMOUNTS chat windows as
 * the user switches pages. If each AgentWindow held its own React state (the old gallery
 * design), switching pages would WIPE that agent's history, and an agent that streams while
 * its window isn't mounted (e.g. the CEO dispatching a specialist while you're on Main) would
 * silently drop events. So the live stream-folding + message history live HERE, once per
 * alias, independent of which window/page is mounted. AgentWindow becomes a stateless VIEW.
 *
 * Each alias subscribes ONCE to the agentBus (fed by App's single /ws). Events fold into a
 * per-alias assistant message via reduceEvent (the same pure logic the gallery used). Windows
 * read via useAgentChat() (useSyncExternalStore) and send via sendMessage().
 */
import { useCallback, useSyncExternalStore } from "react";
import type { ThreadMessageLike } from "@assistant-ui/react";
import { subscribe } from "./agentBus";
import { emptyAssistant, reduceEvent, type AssistantAcc } from "./eventMapping";
import { newConversation, setActiveConversation, getTranscript, type Conversation } from "./conversationsApi";

export interface AgentChatState {
  messages: ThreadMessageLike[];
  isRunning: boolean;
}

interface AgentInternal {
  state: AgentChatState;
  acc: AssistantAcc; // the in-flight assistant turn accumulator
  asstId: string | null; // id of the in-flight assistant bubble (null between turns)
  seq: number;
  listeners: Set<() => void>;
  unsub: () => void;
}

const registry = new Map<string, AgentInternal>();

function accToContent(acc: AssistantAcc) {
  return acc.parts.length ? (acc.parts as any) : [{ type: "text", text: "" }];
}

function emit(it: AgentInternal) {
  for (const l of it.listeners) l();
}

function onEvent(alias: string, ev: any) {
  const it = ensure(alias);
  // start a fresh assistant bubble at the beginning of each turn (after a prior result)
  if (it.asstId === null) {
    const id = `a-${alias}-${it.seq++}`;
    it.asstId = id;
    it.acc = emptyAssistant();
    it.state = {
      messages: [
        ...it.state.messages,
        { role: "assistant", id, content: [{ type: "text", text: "" }] },
      ],
      isRunning: true,
    };
  }
  it.acc = reduceEvent(it.acc, ev);
  const id = it.asstId as string;
  const msg: ThreadMessageLike = { role: "assistant", id, content: accToContent(it.acc) };
  it.state = {
    messages: it.state.messages.map((m) => (m.id === id ? msg : m)),
    isRunning: it.state.isRunning,
  };
  if (ev?.type === "result") {
    it.asstId = null;
    it.state = { messages: it.state.messages, isRunning: false };
  }
  emit(it);
}

function ensure(alias: string): AgentInternal {
  let it = registry.get(alias);
  if (it) return it;
  it = {
    state: { messages: [], isRunning: false },
    acc: emptyAssistant(),
    asstId: null,
    seq: 0,
    listeners: new Set(),
    unsub: () => {},
  };
  registry.set(alias, it);
  it.unsub = subscribe(alias, (ev: any) => onEvent(alias, ev));
  return it;
}

/** Pre-create + subscribe stores for these aliases so NO stream event is missed before a
 *  window mounts (App calls this for every known alias). */
export function ensureAgents(aliases: string[]): void {
  for (const a of aliases) ensure(a);
}

export function getAgentState(alias: string): AgentChatState {
  return ensure(alias).state;
}

export function subscribeAgent(alias: string, cb: () => void): () => void {
  const it = ensure(alias);
  it.listeners.add(cb);
  return () => {
    it.listeners.delete(cb);
  };
}

/** Replace an alias's messages (assistant-ui's external-store setMessages contract). */
export function setAgentMessages(alias: string, messages: ThreadMessageLike[]): void {
  const it = ensure(alias);
  it.state = { messages, isRunning: it.state.isRunning };
  emit(it);
}

/** LOAD a conversation's messages into the window, resetting the in-flight turn (clean switch). */
function loadMessages(alias: string, messages: ThreadMessageLike[]): void {
  const it = ensure(alias);
  it.acc = emptyAssistant();
  it.asstId = null;
  it.state = { messages, isRunning: false };
  emit(it);
}

/** Start a FRESH conversation for `alias`: open it server-side (becomes active) and clear the
 *  window. The next turn the user sends rolls forward in this new conversation. */
export async function startNewConversation(alias: string): Promise<Conversation | null> {
  try {
    const conv = await newConversation(alias);
    loadMessages(alias, []);
    return conv;
  } catch {
    return null;
  }
}

/** RESUME a past conversation: make it active server-side, then load its transcript into the window
 *  (empty if it never ran). The next turn the user sends continues THIS conversation. */
export async function resumeConversation(alias: string, conv: Conversation): Promise<boolean> {
  try {
    await setActiveConversation(alias, conv.session_id ?? conv.id);
    const msgs = conv.session_id ? await getTranscript(alias, conv.session_id) : [];
    loadMessages(alias, msgs);
    return true;
  } catch {
    return false;
  }
}

/** Post a user turn for `alias` to the right endpoint; the reply streams back over /ws → the
 *  bus → this store. CEO → /api/chat {message}; a gym specialist → /api/gym/{alias} {request}. */
export async function sendMessage(alias: string, text: string): Promise<void> {
  const t = (text ?? "").trim();
  if (!t) return;
  const it = ensure(alias);
  it.state = {
    messages: [
      ...it.state.messages,
      { role: "user", id: `u-${alias}-${it.seq++}`, content: [{ type: "text", text: t }] },
    ],
    isRunning: true,
  };
  emit(it);
  const isCeo = alias === "ceo";
  const endpoint = isCeo ? "/api/chat" : `/api/gym/${alias}`;
  const body = isCeo ? { message: t } : { request: t };
  try {
    await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    it.state = { messages: it.state.messages, isRunning: false };
    emit(it);
  }
}

/** React hook — subscribe a component to one alias's live chat state. */
export function useAgentChat(alias: string): AgentChatState {
  const sub = useCallback((cb: () => void) => subscribeAgent(alias, cb), [alias]);
  const get = useCallback(() => getAgentState(alias), [alias]);
  return useSyncExternalStore(sub, get, get);
}
