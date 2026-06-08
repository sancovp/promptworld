/**
 * eventMapping — the LOAD-BEARING pure logic of the PromptWorld frontend.
 *
 * Maps the PromptWorld /ws live event stream (claude -p --output-format stream-json
 * events, re-broadcast by the server as {"alias","event"}) into assistant-ui
 * ThreadMessageLike content parts. Pure (no React/DOM) so it is unit-testable headlessly.
 *
 * stream-json event shapes consumed:
 *   assistant : { type:"assistant", message:{ content:[ {type:"text",text}
 *                                                      | {type:"thinking",thinking}
 *                                                      | {type:"tool_use",id,name,input} ] } }
 *   user      : { type:"user", message:{ content:[ {type:"tool_result",tool_use_id,content,is_error?} ] } }
 *   result    : { type:"result", subtype:"success", result:"..." }   (turn finished)
 *   (system/init, thinking_tokens, compact_boundary, rate_limit_event are ignored here)
 *
 * assistant-ui ThreadMessageLike represents a tool call as ONE "tool-call" part that
 * carries its result INLINE (result/isError on the same part), so a tool_result event
 * is merged back onto the matching tool-call part (by toolCallId), NOT added as a part.
 */

export type AssistantPart =
  | { type: "text"; text: string }
  | { type: "reasoning"; text: string }
  | {
      type: "tool-call";
      toolCallId: string;
      toolName: string;
      args?: unknown;
      result?: unknown;
      isError?: boolean;
    };

export interface AssistantAcc {
  parts: AssistantPart[];
  done: boolean;
}

export const emptyAssistant = (): AssistantAcc => ({ parts: [], done: false });

/** Claude tool_result `content` is a string or an array of {type:"text",text} blocks. */
export function normalizeToolResult(content: unknown): unknown {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((b) =>
        b && typeof b === "object" && (b as any).type === "text" && typeof (b as any).text === "string"
          ? (b as any).text
          : JSON.stringify(b),
      )
      .join("");
  }
  return content;
}

/** Fold ONE /ws stream-json event into the accumulating assistant message. Pure. */
export function reduceEvent(acc: AssistantAcc, ev: any): AssistantAcc {
  const parts: AssistantPart[] = acc.parts.map((p) => ({ ...p }));
  let done = acc.done;
  const type = ev?.type;

  if (type === "assistant") {
    const blocks = ev?.message?.content;
    for (const b of Array.isArray(blocks) ? blocks : []) {
      if (!b || typeof b !== "object") continue;
      if (b.type === "text" && typeof b.text === "string") {
        const last = parts[parts.length - 1];
        if (last && last.type === "text") last.text += b.text; // accumulate streamed text
        else parts.push({ type: "text", text: b.text });
      } else if (b.type === "thinking" && typeof b.thinking === "string") {
        const last = parts[parts.length - 1];
        if (last && last.type === "reasoning") last.text += b.thinking;
        else parts.push({ type: "reasoning", text: b.thinking });
      } else if (b.type === "tool_use") {
        parts.push({
          type: "tool-call",
          toolCallId: String(b.id ?? ""),
          toolName: String(b.name ?? ""),
          args: b.input,
        });
      }
    }
  } else if (type === "user") {
    const blocks = ev?.message?.content;
    for (const b of Array.isArray(blocks) ? blocks : []) {
      if (b && typeof b === "object" && b.type === "tool_result") {
        const id = String(b.tool_use_id ?? "");
        const tc = parts.find(
          (p) => p.type === "tool-call" && (p as any).toolCallId === id,
        ) as Extract<AssistantPart, { type: "tool-call" }> | undefined;
        if (tc) {
          tc.result = normalizeToolResult(b.content);
          if (b.is_error) tc.isError = true;
        }
      }
    }
  } else if (type === "result") {
    done = true;
  }

  return { parts, done };
}

/** Fold a whole event sequence (convenience for tests / replay). */
export function reduceEvents(events: any[]): AssistantAcc {
  return (events ?? []).reduce(reduceEvent, emptyAssistant());
}

/**
 * DEMUX the /ws stream by alias → one AssistantAcc per agent (the gallery's core logic).
 * Each {alias, event} message folds into ITS alias's accumulator via reduceEvent, so
 * interleaved agents (ceo, skill, ...) build SEPARATE threads. Non-agent messages (no
 * alias, e.g. {type:"file_changed"}) are skipped. Pure → unit-testable headlessly.
 */
export function routeByAlias(
  msgs: Array<{ alias?: string; event?: any } | any>,
): Record<string, AssistantAcc> {
  const out: Record<string, AssistantAcc> = {};
  for (const m of msgs ?? []) {
    const alias = m?.alias;
    if (!alias) continue;
    const ev = m?.event ?? m;
    out[alias] = reduceEvent(out[alias] ?? emptyAssistant(), ev);
  }
  return out;
}
