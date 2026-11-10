# RELPOOL dashboard UI and motion

The dashboard keeps the requested charcoal bento surfaces, purple primary action,
lime status accents, Plus Jakarta Sans UI type and JetBrains Mono object IDs.
UI/UX Pro Max's dashboard, typography and motion guidance informed the refinements;
the project's explicit palette and Astro implementation take precedence over
generic search recommendations.

## Layout and legibility

- Desktop forms use 13px controls, 12px labels and consistent 45px input heights.
- Mobile controls use 16px text, a minimum 44px primary touch area and stacked cards.
- Secondary text has stronger contrast; status labels include text alongside color.
- Object IDs wrap completely. The six-node topology has a labeled keyboard-focusable
  horizontal scroll region, keeping wide identifiers inside its card.
- Audit pagination, filtered export and archive controls remain connected to FastAPI.

## Frontend startup

`npm run build` first uses `scripts/build-client.mjs` to bundle GSAP and application
code into `public/assets/relpool-app.js`, then builds Astro's static HTML and CSS.
Astro copies that bundle to `dist/assets/relpool-app.js`. The browser loads it as a
deferred, self-contained classic script targeting ES2020. Dependencies are bundled;
the browser does not need to resolve npm imports or fetch GSAP from a CDN.

FastAPI serves scripts with `text/javascript; charset=utf-8` and disables caching
for `/assets/`, HTML and API responses. Generated bundles in `public/` are ignored;
the final `dist/` build is retained for `python server.py`.

`bootstrap.ts` initializes the motion controller before the provisioning UI. An API
failure does not stop GSAP. A provisioning startup exception produces a visible
error with its message and a Reload workspace action. Failure to fetch the client
bundle is also reported. This separates script-loading failures from a user-selected
motion setting, rather than labeling every failure as missing GSAP.

## Motion behavior

- A GSAP timeline moves luminous SVG packets along the topology and animates the
  connector dash offset.
- Visible bento cards enter with transform/opacity staggers; presets pulse topology
  nodes after the backend validates their names.
- Compilation shows four progress steps. Output uses a transform/opacity reveal.
- Every fresh visit starts in On and plays automatically. Old persisted Auto/Off
  values are ignored. Auto can be explicitly selected to honor reduced motion;
  Off stops the perpetual flow for the current page session. Reloading starts
  in On again. Replay restarts the entrance and topology pulse.
- Hidden tabs pause the flow; page exit kills its timeline and restores card
  visibility. Returning through the browser's back/forward cache recreates the
  flow, and window focus wakes the GSAP ticker. Media-query listeners also support
  the legacy `addListener` API. Changing preferences kills the old timeline before
  creating the next one.

## Verification

Run `npm run build`, `npm run check` and `npm test` inside `web/`.
`tests/client-runtime.test.mjs` executes the shipped bundle in an isolated DOM and
checks real HTTP asset loading from the shipped HTML, startup, changing packet
coordinates, motion preferences, back/forward-cache recovery, API failure,
startup failure, presets, generation and SSH simulation. These are runtime tests,
not screenshot or real-browser visual verification. Python API tests additionally
check script MIME types and cache headers, plus existing provisioning/audit behavior.

For local development, `npm run dev` starts the client-bundle watcher through the
Vite plugin. Source changes regenerate the classic bundle in `public/assets/`.
After a production rebuild, restart `python server.py` and reload localhost:8000.
