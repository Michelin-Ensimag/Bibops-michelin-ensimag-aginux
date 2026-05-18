# Hero Section Redesign — Mission Control

**Date:** 2026-05-18  
**Scope:** `docs/index.html` — hero section only  
**Audience:** Michelin/ENSIMAG evaluators + general visitors  
**Approach:** Mission Control (Option A) — enhance existing structure, keep amber/dark terminal aesthetic

---

## Summary

Rework the hero landing section of `docs/index.html` to feel "live" and immediately communicate benchmark results. No layout restructuring — same single-column flow. All changes are additive or replace static elements with animated equivalents.

---

## Changes by Element

### 1. Glyph pulse animation
- The `BB` amber square in the topbar gets a slow `box-shadow` keyframe: `glyphPulse 2.4s ease-in-out infinite`
- At 50% keyframe: shadow expands to `0 0 30px rgba(244,184,96,.85), 0 0 50px rgba(244,184,96,.25)`
- This signals "system active" without being distracting

### 2. Boot sequence — staggered fade-in
- Each `.boot .line` gets `opacity:0` + `animation: bootIn .3s ease forwards`
- Delays: line 1 = 0.1s, line 2 = 0.4s, line 3 = 0.7s, line 4 = 1.0s, line 5 = 1.3s
- `bootIn` keyframe: `from { opacity:0; transform:translateX(-8px) }` → `to { opacity:1; transform:none }`
- All subsequent hero elements fade in after 1.6s so the boot sequence lands first

### 3. Animated counters in specs grid
- The four metric values (`21 tickets`, `73.4/100`, `51.2/100`, `8.1/10`) start at `0` on page load
- A `animateCounter(id, target, duration, delay)` function uses `requestAnimationFrame` with a cubic ease-out (`1 - (1-t)³`)
- Counters start after boot completes (delays: 2.3s–2.6s)
- No external library needed — pure JS

### 4. Sparkline column added to specs grid
- Specs grid changes from `repeat(4, 1fr)` to `repeat(4, 1fr) 1fr` (5 columns)
- Fifth column: dark background, two inline `<polyline>` SVG lines (MA = amber, LLM = cyan) with a subtle area fill under the MA line
- A dashed gate line at y=22 (≈60/100 threshold) is shown in dim cream
- Score labels `73.4` and `51.2` are rendered as SVG `<text>` elements
- No Chart.js dependency — raw inline SVG

### 5. System live strip (new row below specs grid)
- Full-width flex row, same max-width as specs grid, border on left/right/bottom (no top — visually extends the grid)
- Five cells: `Eval Engine · online`, `RAG · ChromaDB · ready`, `Racing Arena · 4 teams`, `A2A Probes · 3 agents`, `Judge · gpt-4o · 21 tickets`
- Each cell has a 6px colored dot with `pulse` animation (staggered delays: 0s, 0.4s, 0.8s, 1.2s, 0s)
- Colors: green, amber, cyan, magenta, green

### 6. Score comparison cards (new section, below live strip)
- Two cards side by side (`display:flex; gap:24px`), max-width matching specs grid
- Left card (MA): amber corner brackets, green score `73.4/100`, `✓ PASS` badge, 3 animated mini bar rows (Quality, Security, FinOps)
- Right card (LLM): cyan corner brackets, red score `51.2/100`, `✗ FAIL` badge, same 3 bars
- Center separator: `vs` label + amber `→` arrow + `+22.2` delta in amber
- Bar fills animate in with `fillBar 1s cubic-bezier(.2,.7,.2,1)` on page load
- These cards serve as the "interactive teaser" — they foreshadow Section IV results

### 7. Benchmark progress bar (new, below score cards)
- A slim 4px fill bar, `max-width: 480px`
- Label row: `"Benchmark progress · 21 tickets"` left, `"14/21 pass · composite gate"` right in green
- Fill animates from 0% → 66% (`14/21`) with `fillIn 1.2s cubic-bezier(.2,.7,.2,1)` at 2.9s delay
- Below the bar: three segment labels — `Quality ≥7`, `Security ≥6`, `Validated ✓`
- Color: gradient from cyan → amber → green

### 8. Primary CTA glow ring animation
- `.btn.primary` gets `animation: ctaGlow 2.5s ease 3.5s infinite`
- At 50%: `box-shadow` expands to `0 6px 32px rgba(255,210,63,.65), 0 0 0 3px rgba(244,184,96,.15)`
- Creates a subtle breathing glow ring after all other animations complete

### 9. Ticker — additional entries
- 3 new entries added to the scrolling ticker:
  - `ARENA · Team-C wins · Ψ-attacker blocked 92%`
  - `RAGAS · iter-1→3 avg climb +2.1pts`
  - `CO₂ · MA 0.42g/req · −38% vs baseline`
- Animation duration reduced from 60s to 50s so content moves slightly faster

---

## Animation Timeline

| Delay | Element |
|-------|---------|
| 0.1–1.3s | Boot lines stagger in |
| 1.6s | H1 title fades up |
| 2.0s | Lede paragraph fades up |
| 2.2s | Specs grid fades up |
| 2.3–2.6s | Counters animate to target values |
| 2.5s | Shimmer sweep across specs grid cells |
| 2.6s | Live strip fades up |
| 2.8s | Score comparison cards fade up |
| 2.9s | Benchmark progress bar fills |
| 3.0s | CTAs fade up |
| 3.2s | Scroll cue appears |
| 3.5s+ | CTA glow ring starts looping |

---

## Implementation Constraints

- **No new dependencies** — all animations use CSS keyframes + vanilla JS `requestAnimationFrame`
- **No layout regression** — sections below the hero are untouched
- **Existing CSS variables** used as-is (`--amber`, `--green`, `--red`, `--cyan`, `--grid`, etc.)
- **Data values are hardcoded** from the existing `bibops-data` JSON already embedded in the page — the spec counter targets (`21`, `73.4`, `51.2`, `8.1`) must be read from `#bibops-data` on init rather than hardcoded, to stay in sync with benchmark output
- **Responsive**: specs grid collapses to 2-column at ≤800px (sparkline column moves below); score comparison cards stack vertically at ≤700px

---

## Files Changed

- `docs/index.html` — hero section only (approximately lines 3267–3316 in current file)

---

## Out of Scope

- Sections II–VIII (methodology, adversarial, results, arena, A2A, A/B test, deploy) — unchanged
- No backend changes
- No new data files
