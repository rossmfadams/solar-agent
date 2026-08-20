---
name: Helios
description: An AI agent that screens NY solar sites and reads like a trustworthy field diligence report
colors:
  amber-500: "#DD8018"
  amber-600: "#B4690E"
  amber-700: "#9A6A0C"
  amber-50: "#FBF4E6"
  amber-100: "#F0E3C6"
  green-500: "#3D7A3F"
  green-600: "#2F6B3A"
  red-500: "#B23B2E"
  red-600: "#96311F"
  stone-25: "#FDFCFA"
  stone-50: "#F8F6F1"
  stone-100: "#EEEAE2"
  stone-150: "#E7E2D9"
  stone-400: "#8A8172"
  stone-500: "#6E6656"
  stone-800: "#4A4437"
  stone-900: "#1F1B14"
typography:
  display-lg:
    fontFamily: "'Source Serif 4', Georgia, serif"
    fontSize: "40px"
    fontWeight: 600
    lineHeight: 1.15
  display-md:
    fontFamily: "'Source Serif 4', Georgia, serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.2
  display-sm:
    fontFamily: "'Source Serif 4', Georgia, serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.25
  display-xs:
    fontFamily: "'Source Serif 4', Georgia, serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.3
  body-lg:
    fontFamily: "'Public Sans', -apple-system, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
  body-md:
    fontFamily: "'Public Sans', -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  body-sm:
    fontFamily: "'Public Sans', -apple-system, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  label-md:
    fontFamily: "'Public Sans', -apple-system, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.4
  label-sm:
    fontFamily: "'Public Sans', -apple-system, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
  eyebrow:
    fontFamily: "'Public Sans', -apple-system, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: "0.06em"
rounded:
  sm: "6px"
  md: "10px"
  lg: "12px"
  pill: "999px"
spacing:
  1: "4px"
  2: "8px"
  3: "12px"
  4: "16px"
  5: "20px"
  6: "24px"
  8: "32px"
  10: "40px"
  12: "48px"
  16: "64px"
  20: "80px"
  24: "96px"
components:
  button-primary:
    backgroundColor: "{colors.amber-500}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: "9px 16px"
  button-secondary:
    backgroundColor: "#FFFFFF"
    textColor: "{colors.stone-900}"
    rounded: "{rounded.md}"
    padding: "9px 16px"
  card:
    backgroundColor: "#FFFFFF"
    rounded: "{rounded.lg}"
    padding: "20px"
  input:
    backgroundColor: "#FFFFFF"
    textColor: "{colors.stone-900}"
    rounded: "{rounded.md}"
    padding: "10px 12px"
  tag:
    backgroundColor: "#FFFFFF"
    textColor: "{colors.stone-500}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
---

# Design System: Helios

## Overview

**Creative North Star: "The Analyst's Field Notebook"**

Helios reads like a diligence document, not a SaaS dashboard. The base is warm, paper-toned neutrals (stone, not gray) under a serif display face that gives every heading and score the weight of a printed report; body and UI text stay in a clean grotesque sans so the interface itself never competes with the report it's producing. Color is spent narrowly: amber marks the product's own accent and rating scale, and status colors (success green, warning amber, danger red) are reserved strictly for verdicts on the memo's findings — nothing decorative gets tinted.

Depth is understated. Cards separate from the page mostly through a warm off-white background and a hairline border; shadow appears only as a soft ambient cue (on the base card, and more visibly on floating elements like the address-autocomplete dropdown), never as a heavy drop shadow implying a stacked UI. The system supports a full dark theme (charcoal base, amber accent brightened for contrast) built from the same semantic token names, not a separate palette.

**Key Characteristics:**
- Warm stone neutrals instead of cool gray — paper, not glass
- Serif display type for headings/scores, sans for body/UI — report voice vs. interface voice
- Color reserved for accent and verdict status only; everything else stays neutral
- Flat, border-led surfaces with restrained ambient shadow, not stacked-card depth
- Full light/dark theme parity via shared semantic tokens

## Colors

Warm, editorial-neutral palette (stone base) with a single amber accent and three status colors, each usable in a light and dark theme via semantic tokens.

### Primary
- **Amber** (`--amber-500` #DD8018 light / `--amber-dark-500` #DD8018 dark, brightened to `--amber-dark-300` #F0B043 for stronger emphasis): the one accent color. Used for links, the primary button, active tab underline, focus/running-state indicators, and the star-rating fill. Dark theme swaps `--accent`/`--accent-strong` roles so the accent stays legible on charcoal.

### Neutral
- **Stone** (`--stone-25` #FDFCFA page background → `--stone-900` #1F1B14 primary text, light theme): the paper-toned neutral ramp that carries page background, card surfaces, borders, and all text weights. Dark theme substitutes a charcoal ramp (`--charcoal-900` #211D17 background → `--charcoal-text-primary` #F3EEE4 text) through the same semantic names (`--bg-page`, `--text-primary`, etc.), so components never branch on theme directly.

### Status (verdict colors — used only for scoring/flag outcomes, never decoratively)
- **Success green** (`--green-500` #3D7A3F light / `--green-dark-500` #6FBE72 dark): a dimension or check that clears without concern.
- **Warning amber** (`--status-warning`, mapped to `--amber-600` #B4690E light / `--amber-warn-dark` #E39A3E dark): a dimension with a mild deduction or caveat.
- **Danger red** (`--red-500` #B23B2E light / `--red-dark-500` #E2685A dark): a Hard Disqualifier or serious constraint.

### Named Rules
**The Verdict-Only Color Rule.** Green/amber/red never appear outside a scoring or status context (DimensionCard tone, ProgressChecklist icons, star rating). If a color is describing severity, it's one of these three; if it's UI chrome, it's neutral or the single amber accent.

## Typography

**Display Font:** Source Serif 4 (with Georgia, serif fallback)
**Body/UI Font:** Public Sans (with -apple-system, sans-serif fallback)

**Character:** A serif/sans pairing that reads as "printed report rendered in a modern interface" — the serif carries authority and weight on headings and scores, the grotesque sans stays quiet and efficient everywhere information density matters (labels, body copy, buttons, tabs).

### Hierarchy
- **Display lg** (600, 40px/1.15, Source Serif 4): page-level hero headings.
- **Display md** (600, 28px/1.2, Source Serif 4): section/memo headings.
- **Display sm** (600, 22px/1.25, Source Serif 4): card-level titles, dimension status values.
- **Display xs** (600, 17px/1.3, Source Serif 4): compact serif emphasis (e.g. star rating at `sm` size).
- **Body lg** (400, 16px/1.6, Public Sans): primary reading copy.
- **Body md** (400, 14px/1.6, Public Sans): default UI/body text; the page default.
- **Body sm** (400, 13px/1.5, Public Sans): secondary/helper text, dimension detail lines.
- **Label md** (500, 13px/1.4, Public Sans): form labels, tab labels, buttons (md).
- **Label sm** (500, 12px/1.4, Public Sans): tags, compact buttons, verdict caption.
- **Eyebrow** (500, 12px/1.3, 0.06em tracking, Public Sans): not yet used in a shipped component but reserved for section kickers.

### Named Rules
**The Serif-For-Verdicts Rule.** Any element stating a scored outcome (star rating, dimension status value) renders in the display serif at semibold, even at small sizes — the report's conclusions always get the serif's authority, never the UI sans.

## Layout

Single-column, card-stacked layout at typical content widths (no observed grid system beyond flex stacks). Spacing runs on a 4px-rooted scale (`--space-1` 4px through `--space-24` 96px), used consistently for gaps, padding, and vertical rhythm — component internal padding stays in the 12–20px band (`--space-3`–`--space-5`), while section-level spacing uses the 32px+ steps. Both the input screen and memo detail screen are single-track flows (no persistent sidebar), consistent with the single-site, no-batch product scope.

## Elevation & Depth

Flat and border-led, not stacked. At rest, cards are separated from the page by a 1px hairline border (`--border-default`) and a bare warm-white surface, with only a whisper of ambient shadow (`--shadow-card`: `0 1px 3px rgba(30,25,15,0.06)` light / `0 1px 3px rgba(0,0,0,0.24)` dark) — depth is implied, not asserted. A stronger shadow (`--shadow-elevated`: `0 8px 24px rgba(30,25,15,0.10)` light / `0 12px 32px rgba(0,0,0,0.36)` dark) is reserved for genuinely floating elements — currently only the address-autocomplete suggestion dropdown.

### Shadow Vocabulary
- **Ambient card** (`--shadow-card`): default resting state for every card and content surface.
- **Floating/elevated** (`--shadow-elevated`): popovers and dropdowns that visually detach from the page (e.g. autocomplete suggestions).

### Named Rules
**The Border-First Rule.** Surface separation is a border's job; shadow only reinforces it, and only escalates to `--shadow-elevated` for elements that are genuinely floating above other content, not merely "important."

## Shapes

Rounded but restrained: `--radius-sm` (6px) for the smallest controls, `--radius-md` (10px) for buttons/inputs/dimension cards — the workhorse radius — `--radius-lg` (12px) for outer cards, and `--radius-pill` (999px) for tags. No sharp corners and no heavy rounding; the radius scale stays inside a narrow, consistent band rather than mixing sharp and pill shapes across the same hierarchy level.

## Components

### Buttons
- **Shape:** `--radius-md` (10px), consistent across all variants and sizes.
- **Primary:** amber background (`--accent`), white text, 1px border matching the fill — the only fully color-filled button variant.
- **Secondary:** white/card surface, primary text color, 1px `--border-subtle` border — same shape and padding as primary, differing only in fill.
- **Ghost:** transparent background and border, used for the lowest-emphasis actions.
- **Danger:** filled with `--status-danger`, white text — reserved for destructive actions only.
- **Hover / Disabled:** hover drops opacity to 0.88 (no color shift); disabled drops opacity to 0.45 and switches the cursor — a single opacity mechanism handles both interaction states across every variant.
- **Sizes:** sm/md/lg step through the label typography scale (label-sm → label-md → 600 15px), not just padding — larger buttons get visually heavier text, not just more space.

### Tags
- **Style:** pill-shaped (`--radius-pill`), white background, `--border-subtle` border, `--text-tertiary` text, `label-sm` typography — quiet metadata chips, never accent-colored.
- **State:** optionally a link (`href`), same visual treatment whether static or interactive.

### Cards / Containers
- **Corner Style:** `--radius-lg` (12px).
- **Background:** `--surface-card` (white light / charcoal-800 dark).
- **Shadow Strategy:** `--shadow-card` at rest; `elevated` prop switches to `--shadow-elevated` for cards that need to read as raised (see Elevation & Depth).
- **Border:** 1px `--border-default`, always present — the border, not the shadow, is what defines the card edge.
- **Internal Padding:** `--space-5` (20px) default.

### Inputs / Fields
- **Style:** white/card background, `--radius-md` (10px), 1px `--border-subtle` border, `label-md` field label above the control.
- **Error:** border switches to `--status-danger`; helper text switches to the same red and to the error message.
- **Focus:** no custom focus ring observed beyond the browser default — a gap to close during a future `harden` or `polish` pass rather than an intentional choice.

### Navigation (Tabs)
- **Style:** underline-tab pattern — active tab gets `--text-primary` label color and a 2px `--accent` bottom border; inactive tabs are `--text-muted` with a transparent border. No background fill on either state.

### Dimension Card (signature component)
Reports one screening dimension (e.g. a memo section's verdict) as a small serif-headlined status card: `label-sm` muted eyebrow label, then a bold `display-sm`-weight status value colored by verdict tone (success/warning/danger from the Named Rule above), with optional `body-sm` detail beneath. This is the memo's primary building block for turning a pipeline check into a scannable verdict.

### Verdict Rating (signature component)
A right-aligned star rating (0–5 stars, amber fill vs. `--border-subtle` empty) rendered in serif at `display-xs`/`display-sm` weight with 2px letter-spacing, paired with a `label-md` caption in `--accent-on-soft` reading "{Label} · {score}" (e.g. "Good · 78"). This is the single highest-visibility element on the memo — the star glyphs plus the serif treatment are what makes a numeric score read as a verdict rather than a metric.

### Progress Checklist (signature component)
A vertical list of pipeline steps, each row showing an icon (done ✓ in success green, warning ! in warning amber, running = spinning ring in accent, pending = muted hollow circle) plus a `body-md` label, muted while pending and full-color once active/complete. This is what replaces a blank loading state during the ~90 second pipeline run — see [ADR-0005](docs/adr/0005-sse-progress-streaming.md).

## Do's and Don'ts

### Do:
- **Do** use the display serif (Source Serif 4) for anything stating a verdict or conclusion (scores, dimension statuses, headings) — see the Serif-For-Verdicts Rule.
- **Do** keep status green/amber/red scoped to scoring and pipeline-step outcomes only — see the Verdict-Only Color Rule.
- **Do** let borders (`--border-default` / `--border-subtle`) do the primary work of separating surfaces; use `--shadow-card` as a light reinforcement, not the main mechanism.
- **Do** reach for semantic tokens (`--bg-page`, `--text-primary`, `--accent`, etc.) rather than raw palette values (`--stone-900`, `--amber-500`) in component code, so dark theme continues to work automatically.

### Don't:
- **Don't** introduce a second accent color alongside amber — the palette's restraint (one accent, three status colors, neutral everything else) is load-bearing for the "field notebook" character.
- **Don't** use `--shadow-elevated` for ordinary cards to make them feel "more important" — it's reserved for elements that are genuinely floating above the page (dropdowns, popovers).
- **Don't** mix sharp corners into this system — every shape uses the `--radius-sm`–`--radius-pill` scale; nothing renders with a 0px radius.
- **Don't** style form inputs with a custom focus ring yet without checking accessibility contrast first — the current default-outline behavior is an acknowledged gap, not a pattern to copy uncritically.
