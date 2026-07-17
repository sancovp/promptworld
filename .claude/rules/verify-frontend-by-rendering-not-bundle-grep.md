# Verify Frontend Work By RENDERING The Page, Never By Grepping The Bundle

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

## GEOMETRY IS PART OF THE BAR — render at the REAL viewport + check every region FILLS its correct part of the frame
"Styled" and "elements exist" are NOT enough — the LAYOUT must be geometrically correct: every region occupies
its CORRECT part of the frame, edges ALIGN, proportions are right, and there are NO dead empty bands. This is the
failure that shipped: on Main/Specialist a fixed-width column layout left a ~15% DEAD BLACK BAND down the right
of the frame, the Monaco editor pane was a thin sliver instead of filling the remaining width, and the bottom
Terminal bar spanned full-width while the panels above stopped short (right edges DID NOT line up). The commander
opened the PNG and waved it through as "professional" because the elements looked styled — never checking the
geometry. NON-NEGOTIABLE additions to every render-verify round:
1. **Render at a REAL, REPRESENTATIVE full viewport** — the size a user actually opens (e.g. 1920x1080 AND a
   narrower 1366x768), not a cropped/odd headless default. Layout bugs only appear at the real frame size.
2. **Assert the layout FILLS the frame:** the outermost content container's right edge ≈ viewport width (no dead
   band); the flexible pane (the Monaco editor) actually grows to fill remaining width (assert its width is a
   large fraction of the frame, not a fixed sliver); the bottom bar's right edge ALIGNS with the content above
   it (compare bounding-box `right` values — they must match within a few px).
3. **Commander opens the PNG and explicitly judges GEOMETRY:** scan for dead/empty regions, misaligned edges,
   panes that are too narrow/too wide, things not in the part of the frame they belong. "Is every region in the
   right place and filling its share of the frame?" — if no, it FAILS even if every element is present + styled.
Prefer flex/grid that fills the viewport over fixed-px columns; a fixed-px column is the usual cause of the dead
band. The bar is: a user at full screen sees a frame with NO wasted space and aligned edges.

## Each round writes a FRESH screenshot filename (or overwrites) + assert its mtime is current
A stale screenshot from a prior round, left at a reused filename, can be opened and mislead the visual
check into "still broken" (or "still fixed") when the code has changed. So: every verification round writes
its PNG to a fresh/overwritten path, and whoever opens it confirms the file's mtime is from THIS round
before judging it. Old screenshots are retired, never left to be re-read.

→ Why / history / how-to behind this rule: read the `understand-promptworld-rules` skill.
