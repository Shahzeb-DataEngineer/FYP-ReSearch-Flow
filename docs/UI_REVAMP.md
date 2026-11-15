# UI Revamp - Design Brief (2026-11-14)

The old UI was the initial FYP prototype: black-on-white, sharp corners,
generic gray cards, and unmeasured marketing numbers. This revamp takes its
cues from the modern research tools researchers actually use every day.

## Inspiration (studied 2026-11-14, public pages only)

- **Perplexity** - answer-first, centered search, restrained palette, inline
  citations, generous whitespace. The search box is the hero, not a banner.
- **Elicit** - evidence tables, sentence-level citations, transparent
  "how we know" framing, muted greens, dense but calm data display.
- **NotebookLM** - warm paper background, three clear zones (sources,
  chat, studio), soft rounded cards, nothing shouts.
- **Consensus** - a single clear verdict card on top, then the evidence
  below it. Hierarchy: answer first, sources second.
- **SciSpace / Semantic Scholar** - clean paper cards: title, authors,
  venue, year, citation count, source badge. Scannable in seconds.

## Direction

"Warm paper, one accent, evidence first."

- Search-first, not banner-first. The home page is a question box with
  honest context underneath it.
- Every AI claim is shown with its source next to it. Numbers on the site
  are only numbers the project can actually measure (see Honest stats).
- One accent color used sparingly for actions and active states; everything
  else is ink, paper, and stone neutrals. No garish gradients anywhere.

## Palette

- Paper: `#FAFAF7` page background (warm, NotebookLM-like)
- Surface: `#FFFFFF` cards
- Ink: `#1C1917` (stone-900) primary text
- Muted: `#57534E` (stone-600) secondary text
- Faint: `#E7E5E4` (stone-200) borders, `#F5F5F4` (stone-100) fills
- Accent: `#0F766E` (teal-700) primary actions, links, active states
- Accent soft: `#CCFBF1` (teal-100) / `#F0FDFA` (teal-50) tints
- Accent hover: `#115E59` (teal-800)
- Warning: `#B45309` (amber-700) on `#FFFBEB` (amber-50), used only for
  the AI-unavailable state and retraction warnings
- Danger: `#B91C1C` (red-700) for destructive actions and retracted flags
- Success: `#15803D` (green-700) for verified claims and open-access flags

## Type

- Display (headings, hero): "Fraunces", Georgia, serif. Tight leading,
  semibold. Used for the home hero and page titles only.
- UI (everything else): "Inter", system sans. 14px base, 15px-16px body
  on cards, 12px-13px meta text, semibold 600 for labels.
- Mono: ui-monospace for DOIs, IDs, and model names.

## Shape and elevation

- Cards: `rounded-2xl`, 1px `stone-200` border, `shadow-sm` on hover only.
- Buttons: primary = teal-700 fill, white text, `rounded-full`; secondary =
  white fill, stone-300 border; ghost = transparent.
- Pills/badges: `rounded-full`, 12px, semibold, soft tinted backgrounds.
- Page shell: `max-w-7xl` content, sticky top nav with backdrop blur,
  footer in stone-100.
- Radius scale: sm 8px, md 12px, lg 16px, xl 24px, full for pills.

## Logo

New mark in `frontend/public/logo.svg`: a flowing river of three nodes
joined by one smooth curve inside a teal rounded square. The curve is the
"flow" of research from question to evidence to draft. Works on light
backgrounds and as a favicon. Wordmark: "ReSearch" in ink + "Flow" in teal.
The old `researchLogo.jpg` is no longer referenced by the app.

## Honest stats (home page)

The old "10M+ Research Papers / 500K+ Active Researchers / 99.9% Uptime"
were unmeasured marketing numbers. They are replaced with numbers the
project can stand behind:

- 10 free paper sources (OpenAlex, arXiv, Semantic Scholar, Crossref,
  Europe PMC, PubMed, DOAJ, CORE, PMC, Unpaywall)
- 8 AI workflows (search, summarize, RAG chat, draft, Deep Review,
  PRISMA, citation graph, library)
- $0.00 total cost (local Ollama model, no paid APIs)
- 156 tests passing (suite count at revamp time; update if it changes)

## Per-page changes

- Home: centered question-first hero with serif headline, honest stats,
  feature grid with soft cards, model picker + usage panel in the same
  visual language.
- Results: paper cards become white rounded-2xl cards with a clear title
  hierarchy, source pill, year/venue/authors meta, citation count, and a
  soft hover lift. Filters move into a clean left panel. The detail
  slide-over gets a teal primary action row and a clearer summary section.
- Chat: message bubbles with source chips under each answer, input docked
  at the bottom with a teal send button.
- Deep Review / PRISMA / Citation Graph: form cards with labeled sections,
  progress states, and result cards that match the paper-card language.
- My Library: library stats row, Zotero import card, knowledge-graph panel.
- Model picker / Usage panel: compact cards with a teal active state and a
  $0.00 cost readout.
- Navbar: sticky, blurred, logo mark + wordmark, pill nav links, teal
  primary sign-up button, avatar menu unchanged in behavior.

## Premium layer (v2, 2026-11-15)

The v1 revamp got the look right; v2 takes the structure and interaction
model from the tools researchers now expect to feel premium: Linear,
Raycast, Vercel, Arc, Perplexity and Notion.

### What "best" looks like (studied 2026-11-15, public pages only)

- **Linear** - inverted-L chrome (slim sidebar + thin top bar), dark-first,
  single accent, 100-200ms ease-out transitions, keyboard-first with a
  Cmd+K command palette, skeleton states, dense-but-airy 32px rows, 1px
  borders instead of shadows for hierarchy.
- **Raycast / Arc** - the command palette is the product: fuzzy search,
  grouped actions, keyboard navigation, instant.
- **Vercel / Geist** - restrained neutrals, semantic color tokens, generous
  whitespace with tight information density, Inter throughout.
- **Perplexity** - question-first hero with a soft aurora accent, answers
  with citations, calm content pages.
- **Notion** - collapsible sidebar, localStorage-persisted theme, everything
  reachable from the left rail.

### Direction

"Warm paper by day, focused dark by night, keyboard-first."

- **App shell**: slim 240px icon sidebar (Search, PRISMA Review, Citation
  Graph, My Library, Saved Searches, Pricing) with the logo and a live
  local-model + $0.00 cost footer; slide-over drawer on mobile. The top
  bar is slim and glassy: Cmd+K trigger, theme toggle, user menu.
- **Dark mode**: real dark theme, not an inverted filter. Semantic tokens
  (`paper`, `surface`, `ink`, `muted`, `faint`, `fill`, `accent`, `warn`,
  `danger`, `success`, `info` + soft variants) are CSS variables, so the
  whole UI re-themes by overriding them under `.dark`. Toggle persists in
  localStorage, defaults to the OS preference, and an inline script in
  `index.html` applies it before React mounts (no flash). Accent brightens
  to teal-400 (#2DD4BF) on dark for contrast.
- **Fancy but tasteful**: aurora gradient mesh on the hero only (drifting
  teal/violet/amber blobs, calm content pages), glassy sticky nav,
  `shadow-soft` / `shadow-lift` tokens, 150-300ms cubic-bezier
  transitions, hover lift on cards, staggered `fade-up` hero entrance,
  skeleton loaders on results, polished Cmd+K palette with grouped
  actions, recent searches and live suggestions.
- **Color and type**: teal identity kept and deepened (accent scale +
  semantic success/warning/error/info tokens with soft variants). Display
  serif (Fraunces) for heroes only, Inter for UI. Source badges keep
  their hues in light mode and become translucent tints in dark mode.
- **Logo**: same three-node flow mark; it reads on both themes (teal
  square, white nodes) and keeps its shadow in the sidebar.

### What did not change

Backend behavior is untouched. All routes, API calls, the AI-down banner
retry fix, honest stats, and the model picker / usage panel keep working.
The old `Navbar.jsx` file now holds the slim top bar; navigation moved
into `components/Sidebar.jsx`.


1. AI-down banner false positive: `checkAiReady()` ran once on mount with
   a 5s timeout and raced ~10 parallel source searches against Chrome's
   6-connections-per-host limit, so `/ready` timed out and the banner
   stuck without re-checking. Fixed by retrying `/ready` with backoff and
   re-checking when a search starts, and only showing the banner after two
   consecutive confirmed failures.
2. Unmeasured home stats: removed and replaced with the honest stats above.
