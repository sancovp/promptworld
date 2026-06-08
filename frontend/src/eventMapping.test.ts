import { describe, it, expect } from "vitest";
import { reduceEvent, reduceEvents, emptyAssistant, normalizeToolResult, routeByAlias } from "./eventMapping";

// A realistic tool-using CEO turn over /ws (the shape the server broadcasts).
const TURN = [
  { type: "system", subtype: "init" },
  { type: "assistant", message: { content: [{ type: "thinking", thinking: "let me run it" }] } },
  { type: "assistant", message: { content: [{ type: "tool_use", id: "toolu_1", name: "Bash", input: { command: "echo WSTEST" } }] } },
  { type: "user", message: { content: [{ type: "tool_result", tool_use_id: "toolu_1", content: [{ type: "text", text: "WSTEST" }] }] } },
  { type: "assistant", message: { content: [{ type: "text", text: "Done — output: WSTEST" }] } },
  { type: "result", subtype: "success", result: "Done — output: WSTEST" },
];

describe("eventMapping", () => {
  it("maps a tool-using turn → reasoning + tool-call(with merged result) + text, done", () => {
    const acc = reduceEvents(TURN);
    expect(acc.done).toBe(true);

    const tool = acc.parts.find((p) => p.type === "tool-call") as any;
    expect(tool).toBeTruthy();
    expect(tool.toolName).toBe("Bash");
    expect(tool.toolCallId).toBe("toolu_1");
    expect(tool.args).toEqual({ command: "echo WSTEST" });
    expect(tool.result).toBe("WSTEST"); // tool_result merged onto the tool-call part
    expect(tool.isError).toBeUndefined();

    const text = acc.parts.find((p) => p.type === "text") as any;
    expect(text.text).toContain("WSTEST");

    const reasoning = acc.parts.find((p) => p.type === "reasoning") as any;
    expect(reasoning.text).toContain("run it");

    // order preserved: reasoning before tool-call before final text
    const order = acc.parts.map((p) => p.type);
    expect(order.indexOf("reasoning")).toBeLessThan(order.indexOf("tool-call"));
    expect(order.indexOf("tool-call")).toBeLessThan(order.indexOf("text"));
  });

  it("accumulates streamed text blocks into a single text part", () => {
    let acc = emptyAssistant();
    acc = reduceEvent(acc, { type: "assistant", message: { content: [{ type: "text", text: "Hello " }] } });
    acc = reduceEvent(acc, { type: "assistant", message: { content: [{ type: "text", text: "world" }] } });
    const texts = acc.parts.filter((p) => p.type === "text");
    expect(texts.length).toBe(1);
    expect((texts[0] as any).text).toBe("Hello world");
  });

  it("flags isError + string result on a failed tool", () => {
    let acc = emptyAssistant();
    acc = reduceEvent(acc, { type: "assistant", message: { content: [{ type: "tool_use", id: "t2", name: "Bash", input: {} }] } });
    acc = reduceEvent(acc, { type: "user", message: { content: [{ type: "tool_result", tool_use_id: "t2", content: "boom", is_error: true }] } });
    const tc = acc.parts.find((p) => p.type === "tool-call") as any;
    expect(tc.isError).toBe(true);
    expect(tc.result).toBe("boom");
  });

  it("ignores non-render events (init/thinking_tokens/result-only)", () => {
    let acc = emptyAssistant();
    acc = reduceEvent(acc, { type: "system", subtype: "init" });
    acc = reduceEvent(acc, { type: "system", subtype: "thinking_tokens" });
    expect(acc.parts.length).toBe(0);
    expect(acc.done).toBe(false);
    acc = reduceEvent(acc, { type: "result", subtype: "success", result: "x" });
    expect(acc.done).toBe(true);
    expect(acc.parts.length).toBe(0);
  });

  it("normalizeToolResult joins text blocks / passes strings", () => {
    expect(normalizeToolResult("hi")).toBe("hi");
    expect(normalizeToolResult([{ type: "text", text: "a" }, { type: "text", text: "b" }])).toBe("ab");
  });

  it("routeByAlias DEMULTIPLEXES interleaved agents into separate per-alias threads", () => {
    // a mixed /ws stream: ceo and skill events INTERLEAVED, plus a non-agent message
    const stream = [
      { alias: "ceo", event: { type: "assistant", message: { content: [{ type: "text", text: "Let me ask the skill specialist." }] } } },
      { alias: "skill", event: { type: "assistant", message: { content: [{ type: "tool_use", id: "t1", name: "Bash", input: { cmd: "ls" } }] } } },
      { type: "file_changed", path: "a.txt" }, // non-agent → ignored
      { alias: "skill", event: { type: "user", message: { content: [{ type: "tool_result", tool_use_id: "t1", content: "ok" }] } } },
      { alias: "skill", event: { type: "assistant", message: { content: [{ type: "text", text: "I build Skills." }] } } },
      { alias: "ceo", event: { type: "assistant", message: { content: [{ type: "text", text: " It builds Skills." }] } } },
      { alias: "ceo", event: { type: "result", subtype: "success" } },
      { alias: "skill", event: { type: "result", subtype: "success" } },
    ];
    const byAlias = routeByAlias(stream);

    expect(Object.keys(byAlias).sort()).toEqual(["ceo", "skill"]); // file_changed excluded
    // ceo thread: only its two text fragments, accumulated; done
    expect(byAlias.ceo.done).toBe(true);
    const ceoText = byAlias.ceo.parts.find((p) => p.type === "text") as any;
    expect(ceoText.text).toBe("Let me ask the skill specialist. It builds Skills.");
    expect(byAlias.ceo.parts.some((p) => p.type === "tool-call")).toBe(false); // skill's tool did NOT leak into ceo
    // skill thread: its OWN tool-call (with merged result) + its own text; done
    const skillTool = byAlias.skill.parts.find((p) => p.type === "tool-call") as any;
    expect(skillTool.toolName).toBe("Bash");
    expect(skillTool.result).toBe("ok");
    const skillText = byAlias.skill.parts.find((p) => p.type === "text") as any;
    expect(skillText.text).toBe("I build Skills.");
    expect(byAlias.skill.done).toBe(true);
  });
});
