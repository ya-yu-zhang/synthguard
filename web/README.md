# SynthGuard web UI

React 19 + TypeScript + Tailwind CSS 4 + shadcn/ui, built with Vite. The Python server
(`synthguard ui`, [`src/synthguard/ui_server.py`](../src/synthguard/ui_server.py)) serves
the build and the JSON API; this folder is only needed to change the UI.

## Develop

Node 22 (any recent LTS works). `.npmrc` points at the npmmirror registry because
npmjs.org times out from the office network; `package-lock.json` pins every package with
its integrity hash.

```bash
cd web
npm ci
npm run dev        # http://localhost:5173, proxies /api to synthguard ui on :8765
```

Run `synthguard ui` alongside it for the API.

## Ship

```bash
npm run build      # type-check, then write ../src/synthguard/ui_static/
```

Commit the rebuilt `src/synthguard/ui_static/` together with the source change: the
deploy machine and colleagues' machines use that build and never run Node.
`tests/test_ui_server.py` checks the committed build is complete.

## Layout

| path | what |
|---|---|
| `src/index.css` | design tokens (colors, radius, fonts) for light and dark |
| `src/components/ui/` | shadcn/ui components (copied in; edit freely) |
| `src/components/app-shell.tsx` | global nav, phone menu, footnote footer; add a page to `NAV` |
| `src/components/bits.tsx` | page bar (`LocalNav`), hero, ribbon, arrow links, footnote markers |
| `src/pages/` | one file per page |
| `src/lib/api.ts` | typed client; shapes mirror `ui_server.py` |
| `src/app-context.tsx` | polling, running job, theme |

Adding a page: create `src/pages/<name>.tsx`, add it to `Page` in `src/lib/route.ts`,
render it in `src/main.tsx`, and add a `NAV` entry.

Design notes: the language of a product website, not a dashboard. A thin frosted global
nav, a per-page bar with one pill action, headline-led sections that alternate white and
`--alt` grey, a configurator for generation (option rows with the cost on the right, a
summary bar at the bottom), big-number stats, and footnotes in the footer. One blue for
actions, orange only for "try this / needs attention". Inter (bundled) stands in for the
system font on Windows; Macs use their own. No third-party logos, product names or fonts.
Every surface uses the tokens, never raw colors, except the deliberately dark showcase
(running job, image viewer), which is dark in both themes.
