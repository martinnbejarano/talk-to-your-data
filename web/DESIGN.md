---
name: Compliance conversacional
description: A paper-white conversational surface where one sentence answers, and a ledger underneath defends it.
colors:
  papel: "#fbfbfa"
  blanco: "#ffffff"
  burbuja: "#f2f2f0"
  tinta: "#1b1c1e"
  tinta-2: "#55585c"
  tinta-3: "#6e7379"
  linea: "#e7e7e4"
  linea-fuerte: "#d6d7d2"
  acento: "#3651c9"
  acento-hover: "#2b41a6"
  acento-suave: "#eef1fd"
  supuesto-tinta: "#7a5510"
  supuesto-fondo: "#fcf6e9"
  supuesto-linea: "#ecdfc2"
  hueco-tinta: "#3e4658"
  hueco-fondo: "#f1f2f6"
  hueco-linea: "#dcdfe8"
  falla-tinta: "#8c2f26"
  falla-fondo: "#fcf1ef"
  falla-linea: "#eed6d2"
typography:
  display:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.55
    letterSpacing: "-0.018em"
  headline:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "19px"
    fontWeight: 400
    lineHeight: 1.62
    letterSpacing: "-0.006em"
    fontVariant: "tabular-nums"
  title:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "13.5px"
    fontWeight: 600
    lineHeight: 1.55
    letterSpacing: "normal"
  body:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
    fontFeature: "cv05"
  secondary:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "14px"
  bubble: "16px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "22px"
  xl: "24px"
  "2xl": "28px"
  "3xl": "32px"
  "4xl": "44px"
components:
  composer:
    backgroundColor: "{colors.blanco}"
    textColor: "{colors.tinta}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: "8px 8px 8px 14px"
  send-button:
    backgroundColor: "{colors.acento}"
    textColor: "{colors.blanco}"
    rounded: "9px"
    height: "34px"
    width: "34px"
  send-button-disabled:
    backgroundColor: "{colors.linea-fuerte}"
    textColor: "{colors.tinta-3}"
  button-quiet:
    backgroundColor: "{colors.blanco}"
    textColor: "{colors.tinta-2}"
    rounded: "7px"
    padding: "6px 12px"
    size: "13.5px"
  button-quiet-hover:
    textColor: "{colors.tinta}"
  button-quiet-expanded:
    backgroundColor: "{colors.burbuja}"
    textColor: "{colors.tinta}"
  option:
    backgroundColor: "{colors.blanco}"
    textColor: "{colors.tinta}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "11px 14px"
  option-hover:
    backgroundColor: "{colors.acento-suave}"
    textColor: "{colors.tinta}"
  suggestion-chip:
    backgroundColor: "{colors.blanco}"
    textColor: "{colors.tinta-2}"
    rounded: "{rounded.pill}"
    padding: "8px 16px"
    size: "14px"
  question-bubble:
    backgroundColor: "{colors.burbuja}"
    textColor: "{colors.tinta}"
    typography: "{typography.body}"
    rounded: "{rounded.bubble}"
    padding: "9px 15px"
  notice-assumption:
    backgroundColor: "{colors.supuesto-fondo}"
    textColor: "{colors.supuesto-tinta}"
    typography: "{typography.secondary}"
    rounded: "{rounded.md}"
    padding: "11px 14px"
  notice-gap:
    backgroundColor: "{colors.hueco-fondo}"
    textColor: "{colors.hueco-tinta}"
    typography: "{typography.secondary}"
    rounded: "{rounded.md}"
    padding: "11px 14px"
  notice-failure:
    backgroundColor: "{colors.falla-fondo}"
    textColor: "{colors.falla-tinta}"
    typography: "{typography.secondary}"
    rounded: "{rounded.md}"
    padding: "11px 14px"
  provenance-strip:
    backgroundColor: "{colors.burbuja}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.md}"
    padding: "12px 14px"
---

# Design System: Compliance conversacional

## Overview

**Creative North Star: "The Ledger Behind the Sentence"**

The surface is a conventional AI-chat column executed at full fidelity, and that convention is a decision, not a default. The direction round's standing exit was taken deliberately: a compliance officer running a long working day should spend zero attention learning where things are, so the shell borrows the shape they already know from ChatGPT — sticky context bar, one centred column, sticky composer at the bottom — and spends its entire craft budget on the one thing no chat product has: the ledger that opens underneath the answer when the officer has to defend the number. ChatGPT and Linear are the named craft bar; this is not a lower-ambition world, it is ambition pointed at the second screenful instead of the first.

The ground is paper white (#fbfbfa) with white only where something is interactive or liftable. Structure is carried by hairline rules, never by cards: the answer, the derivation ledger, the rows table and the trace line stack in one 46rem measure separated by 1px lines, so a screen full of numbers reads like a printed working paper rather than a dashboard. Type is Inter throughout with tabular numerals on every figure, so digits line up column-wise and a changing counter never reflows the sentence around it. One indigo accent (#3651c9) does all the pointing — send, focus, the proportional bar in the ledger — and nothing else is coloured for decoration.

The world it replaced is the confirmed anti-reference: a denser two-column panel that put derivation, definitions, exclusions and rows in front of the officer simultaneously. Everything that panel showed still exists here; it is one disclosure deep, in audit order — what was counted first, the arithmetic second — because the criterion decides whether a number is right and the arithmetic only matters once the criterion has convinced.

**Key Characteristics:**
- Light mode only, by the user's binding pin: no dark branch, no `prefers-color-scheme` colour block anywhere in the stylesheet.
- One centred 46rem column, no sidebar, ever.
- Flat by default: the composer's lift is the only shadow in the system.
- Hairline rules (#e7e7e4) as the sole structural device; no cards, no fills for grouping except the two burbuja-grey information strips.
- Tabular numerals everywhere a figure appears, including the "thinking" seconds counter.
- Three semantic notice colours — amber assumption, slate gap, red failure — kept strictly distinct in meaning.

## Colors

A near-monochrome paper palette with one indigo accent and three narrow semantic bands, tuned so that "we cannot answer this" never wears the colour of "something broke".

### Primary
- **Indigo Signal** (`{colors.acento}`): the single accent. It paints the send button, the focus outline and focus ring, the caret in the composer, and the proportional scale bar in the derivation ledger. Nothing decorative gets it.
- **Indigo Pressed** (`{colors.acento-hover}`): hover state of the send button only.
- **Indigo Wash** (`{colors.acento-suave}`): the tint behind a hovered option, the composer's 3px focus ring, and text selection. It is the accent at reading strength, never a surface for a whole block.

### Secondary
- **Declared-Assumption Amber** (`{colors.supuesto-tinta}` on `{colors.supuesto-fondo}`, hairline `{colors.supuesto-linea}`): the notice that says the system chose a reading for you. Warm, mid-strength, deliberately not red — the answer is valid, its interpretation is just one of several.
- **Unanswerable Slate** (`{colors.hueco-tinta}` on `{colors.hueco-fondo}`, hairline `{colors.hueco-linea}`): the notice for "there is no number here, and it is not zero". Cool, quiet, and pointedly not red because this is a limit of the data, not a fault of the program.
- **Program-Failure Red** (`{colors.falla-tinta}` on `{colors.falla-fondo}`, hairline `{colors.falla-linea}`): reserved for the request actually failing — a dead backend, a rejected call. This is the only red in the system.

### Neutral
- **Paper** (`{colors.papel}`): the page ground and the sticky bar's own background, so the bar dissolves into the page and only its bottom hairline shows it is there.
- **Surface White** (`{colors.blanco}`): reserved for things that can be acted on or lifted — the composer, option buttons, quiet buttons, the hovered institution select. White is a signal of interactivity, not a background.
- **Grey Strip** (`{colors.burbuja}`): the asked-question bubble, the provenance strip under a definition, table headers, inline code chips, and the expanded state of a quiet button. It is the "this is reference material, not the answer" fill.
- **Ink** (`{colors.tinta}`): body and answer text, figures in the ledger, the 2px rule above a result row.
- **Ink Secondary** (`{colors.tinta-2}`): section headings, step labels, supporting prose, the cut-date line.
- **Ink Tertiary** (`{colors.tinta-3}`): deltas, glosses, placeholders, chevrons, the footnote under the composer, and the muted bar of a zeroed step.
- **Hairline** (`{colors.linea}`): every structural rule — between turns, between ledger rows, between table rows, above the trace line.
- **Hairline Strong** (`{colors.linea-fuerte}`): borders on things you can click — composer, options, quiet buttons — and the scrollbar thumb.

### Named Rules
**The One Accent Rule.** Indigo marks action, focus, and proportion. If a new element is not a control, a focus state, or a quantity being drawn to scale, it does not get the accent.

**The Red-Is-For-Breakage Rule.** Red means the program failed. A question that cannot be answered from the data is slate; a question answered under a declared assumption is amber. Recolouring either of them red would tell a compliance officer that rigour is an error.

**The White-Means-Touchable Rule.** Paper is the ground; white is what you can act on. Do not introduce white cards for grouping — grouping is a hairline's job.

## Typography

**Display / Body / Label Font:** Inter (variable, optical sizes 14–32, weights 400/500/600), with `-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif` behind it.
**Mono Font:** JetBrains Mono (400/500), with `ui-monospace, SF Mono, Menlo, monospace` behind it — used only for the trace id, the raw error string, and inline code.

**Character:** One neutral, high-legibility grotesque doing every job, differentiated by size and weight rather than by family. Body text runs `font-feature-settings: "cv05"` (Inter's alternate lowercase l) so an "l" cannot be misread as a "1" in a screen where the difference is a number an auditor will defend.

### Hierarchy
- **Display** (600, 24px, tight -0.018em; 21px ≤640px): the empty state's single headline. It appears once per session and nowhere else.
- **Headline** (400, 19px/1.62, -0.006em, tabular; 17.5px ≤640px): the answer sentence. This is the largest thing in an answered turn on purpose — the whole thesis is one sentence, so the sentence outranks every heading around it.
- **Title** (600, 13.5px, ink-secondary): section headings inside the disclosure ("Qué se contó", "Cómo se llegó a…"). Deliberately smaller than the body text they introduce: they are wayfinding for an auditor scanning, not content.
- **Body** (400, 15px/1.55): the composer, the asked question, options, the empty state's paragraph.
- **Secondary** (400, 14px/1.5): notice blocks, ledger step labels and figures, definitions, exclusions.
- **Label** (400, 12.5–13px, ink-tertiary): deltas, glosses, unit captions, the composer footnote, the trace line.
- **Mono** (400, 12px): trace ids and raw error strings only.

### Named Rules
**The Inter Rule.** Inter is a deliberate commitment, not a default, and it is a knowing override of the "overused font" finding. The world's chosen canon is the modern product-UI standard, Linear ships Inter, and a distinctive face here would buy character at the cost of the digit legibility this screen exists to protect. Do not swap it for a "more original" grotesque.

**The Tabular Numeral Rule.** Every rendered figure carries `font-variant-numeric: tabular-nums` — the answer sentence, ledger figures and deltas, option counts, table cells, provenance values, the seconds counter. Numbers in this product get compared column-wise and re-read; proportional digits would let a value shift under the eye between two readings of the same screen.

**The Sentence-Outranks-The-Heading Rule.** No heading in an answered turn may be set larger or heavier than the answer sentence. If a new section needs more presence, give it space, not size.

## Layout

One column, always centred, `max-width: 46rem`, with 24px side padding (16px ≤640px). There is no sidebar and no second column; the replaced design's two-column panel is the anti-reference.

The shell is a `100dvh` flex column: a sticky context bar on top (`z-index: 3`, paper background, bottom hairline, 52px min-height / 48px ≤640px) carrying the institution select on the left and the data cut-date on the right; a flexible thread in the middle; and a sticky composer at the bottom (`z-index: 2`) whose background is a transparent-to-paper gradient over its top 22px so content scrolling underneath fades rather than cuts. When the thread is empty it centres itself vertically, so the empty state sits in the optical middle of the viewport instead of hanging from the bar.

Turns stack with 44px of bottom padding (32px ≤640px); consecutive turns are separated by a 1px hairline plus 36px of top padding (26px ≤640px). The asked question is a right-aligned bubble at 85% max width (92% ≤640px); the answer is full-measure and left-aligned — the asymmetry alone tells you who is speaking, with no avatars and no name labels.

Vertical rhythm inside an answer is a small ladder: 18–22px between the sentence and what follows it, 22px into an opened disclosure, 28px between disclosure sections, 24px before the deepest level (rows table, trace line). Horizontal rhythm is 8/12/14/16px.

Responsive behaviour is one breakpoint (640px) plus one input-modality query. `@media (pointer: coarse)` raises `.boton` to a 44px min-height with 16px inline padding and `.opcion` to a 44px min-height. **Keep this rule and any control added to it in sync:** at rest these controls are 30–40px tall, which is the correct density for a mouse in a long working session and a failing tap target on a phone; the coarse-pointer query is what lets the desktop density stay tight. Density is not a token here — it is two different resting sizes for two different pointers.

### Named Rules
**The One-Measure Rule.** Everything — bar, thread, composer, tables — lives inside the same 46rem `.columna`. New surfaces get the same wrapper; nothing goes full-bleed and nothing gets its own width.

**The Coarse-Pointer Floor Rule.** Any new pressable control must be added to the `@media (pointer: coarse)` block with a 44px minimum. Desktop density is bought by that rule existing; a control that skips it ships a target too small to hit.

## Elevation & Depth

The system is flat. Depth is carried by hairlines, by the paper/white ground split, and by z-order on the two sticky regions. There is exactly one shadow, on the composer, because it is the only element that must read as floating over scrolling content.

### Shadow Vocabulary
- **Composer lift** (`box-shadow: 0 1px 2px rgba(27,28,30,0.04), 0 8px 24px -12px rgba(27,28,30,0.14)`): the resting composer. A tight contact shadow plus a wide, heavily negative-spread ambient — visible as separation, never as a drop shadow.
- **Composer focus** (`box-shadow: 0 0 0 3px var(--acento-suave), 0 8px 24px -12px rgba(27,28,30,0.16)`, with border → accent): focus-within. The ring is the accent wash, not a glow.
- **Scroll affordance** (four layered gradients on the rows table wrapper, `background-attachment: local, local, scroll, scroll`): white fades at both edges plus two radial shadows at `rgba(27,28,30,0.12)`, which appear only when the table is actually scrolled. This is a horizontal-overflow cue, not elevation; it is the only place shadow appears inside content.

### Named Rules
**The One Shadow Rule.** The composer's lift is the system's only elevation. New surfaces — notices, options, tables, disclosure panels — are flat and are separated by hairlines. If something needs to feel raised, ask instead whether it needs to be white on paper.

## Shapes

A soft-rectangular language on a tight radius ladder, scaled to the element's size rather than to a style tier: 4px for the focus ring and inline code, 6px for the institution select, 7px for quiet buttons, 8px for notices, options, the provenance strip and the rows-table wrapper, 9px for the square send button, 14px for the composer, 16px for the asked-question bubble, and a full pill (999px) for the empty state's suggestion chip — the one place a control is meant to read as an invitation rather than a field.

Borders are 1px and hairline-coloured; the only thicker rule in the system is the 2px ink line above a ledger result row, which is the accounting convention for a total and reads as such. Icons are five hand-drawn 16px SVGs on a shared 1.5 stroke with round caps and joins, inheriting `currentColor` — no icon font, no icon package, no glyph characters.

### Named Rules
**The Radius-Follows-Size Rule.** A control's radius tracks its height, not its importance. A new 34px control takes ~9px; a new 14px inline chip takes 4px. Do not introduce a new radius tier for emphasis.

## Components

### Composer
- **Character:** The one lifted object on the page; everything else is printed on it.
- **Shape:** Generously rounded (14px), 1px hairline-strong border, white on paper, 8px padding with a 14px left inset so text starts clear of the corner.
- **Behavior:** A single-row `textarea` auto-grown to its scroll height on every keystroke, capped at 40vh, so a long question is fully visible before it is sent. Enter sends, Shift+Enter breaks a line.
- **Focus:** Border shifts to accent and a 3px accent-wash ring appears (140ms). The caret is accent-coloured.
- **Disabled (answering):** Text dims to ink-secondary and the placeholder changes to say the previous question is still being answered.
- **Send:** A 34px accent square (9px radius) with a 17px arrow. Disabled it goes hairline-strong on ink-tertiary — greyed, not hidden, so its position stays learnable.
- **Footnote:** 12px ink-tertiary, centred beneath, stating that every answer is computed against the selected institution at the cut date.

### Buttons
- **Quiet button** (the only button variant besides send): white on hairline-strong, 7px radius, 6px/12px padding, 13.5px medium ink-secondary, with a chevron caret.
- **Hover:** text to ink, border to ink-tertiary. 120ms.
- **Expanded** (`aria-expanded="true"`): fills grey-strip, text to ink, and the caret rotates 180° over 240ms on the system easing.

### Chips
- **Suggestion chip:** the empty state's single suggested question — pill radius, white, 8px/16px, 14px ink-tertiary text going to ink on hover. It reuses the option's border and hover treatment, so the first thing a new user clicks teaches the affordance for every clarification option they will meet later.

### Options (clarification answers)
- **Style:** Full-width white rows, 8px radius, hairline-strong border, 11px/14px padding, question text baseline-aligned left against an optional tabular count right.
- **Hover:** border to accent, background to accent wash.
- **Disabled:** 55% opacity, default cursor.
- **Rule:** options are never placed behind a disclosure. When the system asks back, the options *are* the answer.

### Notice blocks
- **Character:** Flat tinted rectangles, 8px radius, 1px tinted border, a 16px stroked icon flush left at the top, 14px text — three of them, one per non-plain answer state.
- **Assumption (amber):** "the system chose a reading for you", with the chosen reading spelled out. Never behind a disclosure — it is a condition of the sentence above it, not supporting detail.
- **Unanswerable (slate):** no red, no alert triangle. Its icon is a dashed circle with a minus — an absence, drawn as an absence.
- **Failure (red):** alert triangle, plus the raw error in 12px mono at 85% opacity. Carries `role="alert"`.

### Provenance strip
- **Style:** Grey-strip fill, 8px radius, 12px/14px padding, an auto-fit grid of `minmax(150px, 1fr)` columns.
- **Content:** 12px ink-tertiary term over a 13.5px medium ink value, tabular. It sits under each definition and answers where a threshold came from and since when.

### Tables (query rows)
- **Style:** Hairline-bordered 8px wrapper with horizontal overflow, 13px tabular text, 7px/12px cells, `white-space: nowrap`.
- **Header:** sticky, grey-strip fill, 500 weight ink-secondary.
- **Rows:** hairline bottom rule, dropped on the last row so the border never doubles with the wrapper.
- **Depth:** the rows table lives one disclosure deeper than everything else, inside a native `<details>` whose marker is suppressed — it is the heaviest thing on the screen to read.

### Navigation
There is none in the conventional sense. The sticky bar carries only state: an appearance-stripped institution `<select>` set in 600-weight body text with a chevron, so it reads as a title until hovered (white fill, hairline-strong border appears), and the cut date at 13px on the right. Both are visible in every state, including states that carry no number, because "this year" has to be interpreted against the cut date and not the reader's calendar.

### The Derivation Ledger (signature component)
The one place the system spends beyond the category standard. Each step is a two-column grid — label left in ink-secondary, tabular figure right in ink — on 7px vertical padding with a hairline bottom rule, plus an optional 12px ink-tertiary delta on the second column's own line saying how many were dropped. Nested filter steps indent 14px; steps that are summed do not indent, because they are siblings rather than children. The final row is the accounting total: a 2px ink rule above it, label in medium ink, figure at 16px/600.

Under each row runs a 2px proportional bar in accent at 0.72 opacity (full opacity on the result row, ink-tertiary on a zeroed addend).

**The No-Track Rule.** The scale bar has no track of its own. It is absolutely positioned at `bottom: -1px` and paints *over* the row's existing `border-bottom`, which is already there. A separate track was tried; it put two rules on every row and the ledger read as ruled paper. If you restyle these rows, the bar's `bottom: -1px` and the row's `border-bottom` are one unit — change either and you get the striped result back.

**The Per-Run Scale Rule.** The bar's maximum is computed per *tramo* — per run of steps that count the same unit — by `topeDelTramo` in `derivacion.js`, and never per rendered block. The sum phase splits one run into two rendered blocks; scaling per block would give the result row and the universe row identical full-length bars. The scale also never crosses a unit change, because a bar comparing alerts against clients draws a proportion that means nothing, and the UI says so in prose when more than one run is present.

**The 0.4% Floor Rule.** A nonzero value is drawn at `max(|n| / tope, 0.004)` — never smaller than 0.4% of the row. Without the floor, 660 against 180.000 renders as nothing and the eye reads "none" where there are 660. Zero is exempt and draws nothing: the floor exists for the small, not for the absent.

### Live region
Exactly one `aria-live="polite"` `role="status"` region exists in the entire document, visually hidden, in `App.jsx`. It carries the thinking notice, the failure notice, or the latest answer sentence. One region per turn was tried and failed twice over: opening a disclosure re-announced the whole answer, and the arrival of a new turn never announced at all, because a live region inserted together with its content does not fire. Any new announcement must be routed through this single region — do not add a second one.

## Do's and Don'ts

### Do:
- **Do** keep one centred 46rem column and light mode only. Both are the user's binding pins: no sidebar, no dark branch, no `prefers-color-scheme` block.
- **Do** put every rendered figure on tabular numerals, including counters that tick.
- **Do** paint the derivation scale bar over the row's own `border-bottom` (`bottom: -1px`, no track).
- **Do** compute that scale's maximum per unit run via `topeDelTramo`, never per rendered block, and never let a bar span a unit change.
- **Do** apply the 0.4% minimum width to nonzero values only; a zero draws nothing.
- **Do** route every screen-reader announcement through the single `aria-live` region in `App.jsx`.
- **Do** add every new pressable control to the `@media (pointer: coarse)` 44px block.
- **Do** keep Inter. It is a deliberate canon commitment and a knowing override of the "overused font" finding, and it is what the digit-legibility rules are tuned against.
- **Do** leave the answer sentence as the largest element in an answered turn.
- **Do** use white for things that can be acted on, and hairlines for everything structural.
- **Do** honour `prefers-reduced-motion: reduce` — it is already wired to collapse every animation and transition, including the disclosure's grid animation.

### Don't:
- **Don't** give the scale bar a track, or a second rule appears on every ledger row.
- **Don't** colour the "cannot answer" state red or give it an alert icon. It is slate because it is rigour, not breakage. Red is reserved for the program actually failing.
- **Don't** put clarification options or a declared assumption behind "Mostrar más". Options are the answer; an assumption is a condition of the sentence above it.
- **Don't** show the machine state name (`NO_SE_PUEDE_RESPONDER`, `NECESITO_QUE_ACLARES`) on screen. The state decides what is drawn; the officer sees the consequence, not the label.
- **Don't** add cards or shadows. The composer's lift is the only elevation in the system.
- **Don't** introduce a second `aria-live` region, or per-turn live regions.
- **Don't** add a second column, a sidebar, or a full-bleed surface outside `.columna`.
- **Don't** add an icon library. The five 16px icons are drawn in `Iconos.jsx` on a shared 1.5 stroke; new icons match that spec.
- **Don't** use accent colour decoratively. It marks action, focus, and drawn proportion, and nothing else.
