# A Frontend Dev Agent Works By A RECURSIVE Playwright Screenshot → LOOK → Edit Loop — That IS The Method

A frontend developer agent does NOT build by editing code, asserting on the DOM, and reporting. It builds the
way a human frontend dev does — and the way every multimodal LLM should: a **tight recursive visual loop** where
it **renders the running page, LOOKS at the screenshot with its own eyes, edits from what it sees, and renders
again** — over and over until the page is visually correct. **Looking at the rendered image is EVERY iteration's
driver, not a final check.** The agent is a multimodal model: it can `Read` a PNG and SEE the layout — so it must.

## The loop (the agent runs THIS, continuously, as its primary method)
1. **Run the app with a hot-reloading dev server** (`npm run dev` in `frontend/`, Vite HMR) so each edit reloads
   instantly — a FAST loop, no full image rebuild per iteration.
2. **Launch Playwright** (headless chromium / playwright-core, already available in this repo), load the page at a
   **real viewport** (1920×1080, and also check a narrower 1366×768), and **screenshot to a fresh `/tmp/*.png`**.
   (In this container the headless browser crashes with "Target crashed" on the heavy unbundled dev build unless
   you launch chromium with `--disable-dev-shm-usage` — add that flag.)
3. **READ the screenshot yourself and actually LOOK at it.** Open the PNG (you are multimodal — you can see it) and
   judge what is ACTUALLY on screen: dead/empty bands, misaligned edges, a pane that's a sliver or overflowing,
   anything in the wrong part of the frame, wrong proportions, broken styling.
4. **Edit the code** from what you SAW. HMR reloads.
5. **Screenshot again. READ it again. LOOK again.** Compare to the previous shot — did it actually change / improve?
6. **REPEAT** until the page is visually correct (frame filled, edges aligned, every region in its right place) at
   every viewport — THEN commit and report (commit SHA + the final screenshot paths you looked at).

## What this is NOT (the banned non-methods)
- **NOT** "edit → assert the DOM has `<pre><code>` / `ul li == 3` → report." DOM-element-exists is not seeing the page.
- **NOT** bundle-grep ("the class is in the built JS"). That proves nothing about what renders.
- **NOT** "render once at the end and open one screenshot." The screenshot-look happens EVERY iteration and DRIVES
  the edits; it is not a closing checkbox.
- **NOT** "report screenshots for the commander to open instead of looking yourself." YOU look, every loop.

→ Why / history / how-to behind this rule: read the `understand-promptworld-rules` skill.
