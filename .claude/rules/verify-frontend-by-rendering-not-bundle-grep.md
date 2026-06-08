# Verify Frontend Work By RENDERING The Page, Never By Grepping The Bundle — NON-NEGOTIABLE

A frontend's real surface is the **RENDERED PAGE IN A BROWSER**, not strings in a built JS/CSS file.
"The class name / the import is in the bundle" proves NOTHING about whether the UI renders, looks right,
or works. (This is the same mistake as "curl proves the MCP works" — it is the wrong surface.)

## The rule
To verify ANY frontend change, RENDER it and look:
1. Boot the app (or serve the exact `dist/`), open it in a **headless browser** (playwright / puppeteer /
   headless-chromium — already used in this repo; it produces a PNG).
2. **SCREENSHOT** the relevant states to `/tmp/*.png`.
3. **Assert on the LIVE DOM + console**, e.g.:
   - markdown actually rendered → a real `<pre><code>` + `<ul><li>` exist, raw ```` ``` ```` text is ABSENT;
   - the editor has TABS that switch + a real nested explorer; `.monaco-editor` has nonzero size;
   - a panel toggle actually REMOVES the panel from the DOM (screenshot both states);
   - **ZERO console/page errors.**
4. The **commander OPENS the screenshots** (Read the PNG) and judges them at the professional/maximum bar
   before redeploying. A passing screenshot is the only evidence of "done" for UI.

## Honest constraint in THIS env
You cannot render headless INSIDE the jobworld-cave container (no chromium) nor reach the host-published
port from mind_of_god (netns isolation). So render the **byte-identical `dist`** (confirm the served bundle
hashes match the local dist by vite content-hash) via a local server + headless chromium. State that
provenance honestly; the final on-screen judgment is the user's, but the render is the floor — never ship
on bundle-grep.

## A DOM element EXISTING is NOT the same as it being STYLED — judge the VISUAL result
A DOM assertion like "`pre code` exists" or "`ul li` = 3" proves the markup is there — it does **NOT**
prove it looks right. Multiple rounds passed `pre/code/ul exist` while the code block was plain monospace
with no syntax colors / no panel and the list had no bullets. **The bar is the VISUAL appearance in the
screenshot:** code blocks SYNTAX-HIGHLIGHTED in a styled panel, lists with visible BULLET markers, proper
spacing/colors — a professional look. So: after rendering, you must **OPEN the screenshot and confirm it
actually CHANGED / looks styled**, not just that elements exist. "It renders the elements" is the
element-exists trap; "it looks professional in the PNG" is the bar. (Library components often need an
extra piece for the visual — e.g. assistant-ui MarkdownText needs a syntax-highlighter wired in + prose
styling; per `use-libraries-at-maximum-never-hand-roll`, wire ALL of it.)

## Each round writes a FRESH screenshot filename (or overwrites) + assert its mtime is current
A stale screenshot from a prior round, left at a reused filename, can be opened and mislead the visual
check into "still broken" (or "still fixed") when the code has changed. So: every verification round writes
its PNG to a fresh/overwritten path, and whoever opens it confirms the file's mtime is from THIS round
before judging it. Old screenshots are retired, never left to be re-read.

## Why
Bundle-grep passed three broken UI rounds in a row (terminal that didn't collapse, skeleton styles, Monaco
that never rendered) while reporting "verified" — and DOM-element-exists passed two more (unstyled markdown)
while it looked unstyled. Rendering + screenshot + judging the VISUAL appearance is the only check that
reflects what the user actually sees. Composes with `verify-via-user-surface-before-done`.
