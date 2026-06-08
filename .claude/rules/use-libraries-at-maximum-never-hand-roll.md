# Use Named Libraries At Their MAXIMUM — Never Hand-Roll What They Ship Prebuilt — NON-NEGOTIABLE

When a library is specified for a job (e.g. **assistant-ui** for the chat), USE ITS FULL PREBUILT POWER
at the maximum quality level that exists. If something custom/minimal were wanted, the instruction would
be "make X." Naming a library = "use this library properly, completely, at its best."

## The failure this prevents (it kept happening)
- Installed only **`@assistant-ui/react`** (the HEADLESS primitives) and then **hand-rolled** markdown
  (raw `react-markdown` + remark + rehype) and the chat styling (custom CSS) — reinventing exactly what
  assistant-ui ships prebuilt. WRONG. assistant-ui provides, OUT OF THE BOX:
  - **`@assistant-ui/react-markdown`** → the **`MarkdownText`** component = markdown + highlighted code
    blocks, prebuilt. USE IT for the message text part. Do NOT hand-roll react-markdown.
  - its **styled `Thread`** (shadcn/Tailwind component layer) = composer, bubbles, tool cards, scroll —
    prebuilt. USE IT. Do NOT hand-roll a Thread + custom CSS.

## The rules
1. **Install + use the library's PREBUILT component layer**, not just its headless core. If only the
   headless package is installed, that is the tell you are about to hand-roll — STOP and add the prebuilt
   packages.
2. **Version-COHERENT:** every package in a family must be mutually version-compatible. The earlier
   skeleton was `@assistant-ui/styles@0.3.7` against `@assistant-ui/react@0.11` — a mismatch. Pick one
   coherent version set (bump the core if needed and fix the adapter API), never mix incompatible versions.
3. **Never abandon the library to avoid a version bump or an adapter change.** If bumping breaks the
   runtime wiring (e.g. `useExternalStoreRuntime`), FIX the wiring to the new API — do not fall back to
   hand-rolling.
4. **Scope:** the library covers ITS domain at max (assistant-ui = the chat). Things outside its domain
   (the Monaco editor) are separate and may be custom — but THOSE also use their best real source (see
   `porting-heaven-components-rewire-fileservice-to-api-files`).

## Why
Hand-rolling what a maintained library provides is lower-quality, less complete, and unmaintainable — and
it is the exact "minimal stub instead of maximum" failure that forces the user to iterate. Use the library
at full power, version-coherent, every time.
