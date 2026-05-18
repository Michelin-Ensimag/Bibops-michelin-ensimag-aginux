# Hero Mission Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework `docs/index.html` hero section to feel "live" — animated counters, sparkline, live-status strip, score comparison cards, staggered boot sequence, and CTA glow.

**Architecture:** Single-file HTML change — all CSS additions go before `</style>` (line 2756), HTML changes replace the hero section (lines 3267–3314), and a new JS block is inserted before `</body>` (line 6316). No new files, no new dependencies.

**Tech Stack:** Vanilla JS (`requestAnimationFrame`), CSS keyframes, inline SVG — no new libraries.

---

## Data reference (from `#bibops-data` JSON in the page)

These values come from the embedded JSON and are used throughout:

| Key path | Value |
|---|---|
| `diagnostics.ticket_count` | `21` |
| `composite.architectures.systeme_multi_agents.composite_score` | `91.34` |
| `composite.architectures.llm_unique.composite_score` | `46.14` |
| `summary.systeme_multi_agents.score_moyen` | `7.86` |
| `summary.llm_unique.score_moyen` | `2.81` |
| `security.systeme_multi_agents.security_score_moyen` | `9.97` |
| `diagnostics.systeme_multi_agents.score_ge_7_count` | `20` |

---

## Task 1: CSS — animations keyframes + new element styles

**Files:**
- Modify: `docs/index.html` — inject CSS block before line 2756 (`</style>`)

- [ ] **Step 1: Add the CSS block**

Find the exact string `  @media (max-width: 900px){
    #adversarial .adv-body{ grid-template-columns: 1fr; }
    #adversarial .adv-conv{ border-right: none; border-bottom: 1px solid var(--grid); }
    #adversarial .adv-controls{ flex-direction: column; align-items: flex-start; }
    #adversarial .adv-stepper{ margin-left: 0; }
  }
</style>` and replace it with:

```css
  @media (max-width: 900px){
    #adversarial .adv-body{ grid-template-columns: 1fr; }
    #adversarial .adv-conv{ border-right: none; border-bottom: 1px solid var(--grid); }
    #adversarial .adv-controls{ flex-direction: column; align-items: flex-start; }
    #adversarial .adv-stepper{ margin-left: 0; }
  }

  /* ============================================================
     HERO MISSION CONTROL — animations + new elements
     ============================================================ */

  /* Boot stagger */
  @keyframes bootIn { from{opacity:0;transform:translateX(-8px)} to{opacity:1;transform:none} }
  .hero .boot .line { opacity: 0; animation: bootIn .3s ease forwards; }
  .hero .boot .line:nth-child(1){ animation-delay: .10s; }
  .hero .boot .line:nth-child(2){ animation-delay: .40s; }
  .hero .boot .line:nth-child(3){ animation-delay: .70s; }
  .hero .boot .line:nth-child(4){ animation-delay: 1.00s; }

  /* Hero elements cascade in after boot */
  @keyframes heroFadeUp { from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:none} }
  .hero h1.display      { opacity:0; animation: heroFadeUp .55s ease 1.4s forwards; }
  .hero .lede           { opacity:0; animation: heroFadeUp .45s ease 1.85s forwards; }
  .hero .specs          { opacity:0; animation: heroFadeUp .45s ease 2.1s forwards; }
  .hero .live-strip     { opacity:0; animation: heroFadeUp .35s ease 2.4s forwards; }
  .hero .hero-compare   { opacity:0; animation: heroFadeUp .45s ease 2.55s forwards; }
  .hero .bench-status   { opacity:0; animation: heroFadeUp .35s ease 2.75s forwards; }
  .hero .actions        { opacity:0; animation: heroFadeUp .45s ease 2.9s forwards; }
  .hero .scroll-cue     { opacity:0; animation: heroFadeUp .35s ease 3.1s forwards; }

  /* Glyph pulse */
  @keyframes glyphPulse {
    0%,100%{ box-shadow: 0 0 18px rgba(244,184,96,.4); }
    50%{ box-shadow: 0 0 30px rgba(244,184,96,.85), 0 0 50px rgba(244,184,96,.25); }
  }

  /* CTA glow ring */
  @keyframes ctaGlow {
    0%,100%{ box-shadow: 0 4px 20px rgba(244,184,96,.25); }
    50%{ box-shadow: 0 6px 32px rgba(255,210,63,.65), 0 0 0 3px rgba(244,184,96,.15); }
  }

  /* Live strip */
  .hero .live-strip{
    max-width: 1040px; display: flex; gap: 0;
    border: 1px solid var(--grid); border-top: none;
    background: var(--grid);
  }
  .hero .live-strip .lc{
    flex: 1; background: var(--bg-elev); padding: 9px 14px;
    display: flex; align-items: center; gap: 8px;
    font-size: 10px; color: var(--slate);
    text-transform: uppercase; letter-spacing: .12em;
    border-right: 1px solid var(--grid);
  }
  .hero .live-strip .lc:last-child{ border-right: none; }
  .hero .live-strip .lc .ld{
    width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
    animation: pulse 2s ease-in-out infinite;
  }
  .hero .live-strip .lc .ld.gr{ background: var(--green); box-shadow: 0 0 6px var(--green); }
  .hero .live-strip .lc .ld.am{ background: var(--amber); box-shadow: 0 0 6px var(--amber); animation-delay: .4s; }
  .hero .live-strip .lc .ld.cy{ background: var(--cyan); box-shadow: 0 0 6px var(--cyan); animation-delay: .8s; }
  .hero .live-strip .lc .ld.mg{ background: var(--magenta); box-shadow: 0 0 6px var(--magenta); animation-delay: 1.2s; }
  .hero .live-strip .lc .lt{ color: var(--cream-dim); }
  .hero .live-strip .lc .lv{ margin-left: auto; color: var(--amber); font-family: "JetBrains Mono"; font-size: 11px; font-weight: 600; }

  /* Score comparison cards */
  .hero .hero-compare{
    margin-top: 24px; max-width: 1040px;
    display: flex; gap: 24px; align-items: stretch;
  }
  .hero .hc-card{
    flex: 1; background: var(--bg-card); border: 1px solid var(--grid);
    padding: 16px 20px; position: relative;
  }
  .hero .hc-card::before{
    content:""; position:absolute; top:-1px; left:-1px;
    width:10px; height:10px; border-top:1px solid; border-left:1px solid;
  }
  .hero .hc-card.ma::before{ border-color: var(--amber); }
  .hero .hc-card.llm::before{ border-color: var(--cyan); }
  .hero .hc-card .hc-arch{ font-size:9px; color:var(--slate); letter-spacing:.2em; text-transform:uppercase; margin-bottom:3px; }
  .hero .hc-card .hc-name{ font-size:13px; font-weight:600; margin-bottom:10px; }
  .hero .hc-card.ma .hc-name{ color:var(--amber); }
  .hero .hc-card.llm .hc-name{ color:var(--cyan); }
  .hero .hc-card .hc-score{ font-family:"JetBrains Mono"; font-size:40px; font-weight:600; line-height:1; }
  .hero .hc-card.ma .hc-score{ color:var(--green); }
  .hero .hc-card.llm .hc-score{ color:var(--red); }
  .hero .hc-card .hc-score small{ font-size:13px; color:var(--slate); }
  .hero .hc-card .hc-badge{
    display:inline-block; padding:3px 10px; font-size:10px;
    font-weight:600; letter-spacing:.2em; text-transform:uppercase;
    border:1px solid; margin-top:7px;
  }
  .hero .hc-card.ma .hc-badge{ color:var(--green); border-color:var(--green); background:rgba(127,190,154,.08); }
  .hero .hc-card.llm .hc-badge{ color:var(--red); border-color:var(--red); background:rgba(229,103,93,.08); }
  .hero .hc-card .hc-bars{ margin-top:11px; display:flex; flex-direction:column; gap:5px; }
  .hero .hc-bar-row{ display:grid; grid-template-columns:64px 1fr 36px; gap:7px; align-items:center; font-size:9px; }
  .hero .hc-bar-row .hb-k{ color:var(--slate); text-transform:uppercase; letter-spacing:.1em; }
  .hero .hc-bar-row .hb-track{ height:4px; background:var(--bg-deep); border:1px solid var(--grid); position:relative; overflow:hidden; }
  @keyframes fillBar { from{width:0%} }
  .hero .hc-bar-row .hb-fill{ position:absolute; top:0;left:0;bottom:0; animation: fillBar 1s cubic-bezier(.2,.7,.2,1) 2.7s both; }
  .hero .hc-card.ma .hb-fill{ background:var(--amber); }
  .hero .hc-card.llm .hb-fill{ background:var(--cyan); }
  .hero .hc-bar-row .hb-v{ color:var(--cream-dim); text-align:right; font-family:"JetBrains Mono"; font-size:10px; }
  .hero .hc-sep{
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    gap:6px; padding:0 4px;
  }
  .hero .hc-sep .vs{ font-size:10px; letter-spacing:.2em; text-transform:uppercase; color:var(--slate); }
  .hero .hc-sep .delta{ font-size:13px; color:var(--amber); font-weight:600; font-family:"JetBrains Mono"; }

  /* Benchmark progress bar */
  .hero .bench-status{ margin-top:22px; max-width:480px; }
  .hero .bench-status .bs-label{
    display:flex; justify-content:space-between;
    font-size:10px; color:var(--slate); letter-spacing:.15em; text-transform:uppercase; margin-bottom:6px;
  }
  .hero .bench-status .bs-label .pass{ color:var(--green); }
  .hero .bench-status .bs-track{ height:4px; background:var(--bg-elev); border:1px solid var(--grid); position:relative; }
  @keyframes fillIn { from{width:0%} }
  .hero .bench-status .bs-fill{
    position:absolute; top:0;left:0;bottom:0;
    background: linear-gradient(90deg, var(--cyan) 0%, var(--amber) 60%, var(--green) 100%);
    animation: fillIn 1.2s cubic-bezier(.2,.7,.2,1) 2.8s both;
    width: 95.2%;
  }
  .hero .bench-status .bs-segs{
    display:flex; justify-content:space-between; font-size:9px;
    color:var(--slate); letter-spacing:.1em; margin-top:5px; text-transform:uppercase;
  }
  .hero .bench-status .bs-segs span:last-child{ color:var(--green); }

  /* Specs sparkline column */
  .hero .specs .spec-spark{
    background: var(--bg-deep); padding:12px 14px;
    display:flex; flex-direction:column; justify-content:space-between;
  }
  .hero .specs .spark-labels{
    display:flex; justify-content:space-between;
    font-size:9px; color:var(--slate); letter-spacing:.1em; text-transform:uppercase; margin-bottom:5px;
  }
  .hero .specs .spark-labels .ma{ color:var(--amber); }
  .hero .specs .spark-labels .llm{ color:var(--cyan); }

  /* Responsive */
  @media (max-width: 840px){
    .hero .specs{ grid-template-columns: repeat(2, 1fr) !important; max-width: 100% !important; }
    .hero .specs .spec-spark{ grid-column: 1 / -1; }
    .hero .hero-compare{ flex-direction: column; }
    .hero .hc-sep{ flex-direction: row; padding: 4px 0; }
  }
</style>
```

- [ ] **Step 2: Verify CSS loaded**

Open `docs/index.html` in a browser. Open DevTools → Elements and confirm `.hero .live-strip`, `.hero .hero-compare`, `.hero .bench-status` classes are present in the stylesheet. No 404s in the Console tab.

- [ ] **Step 3: Commit**

```bash
git add docs/index.html
git commit -m "feat(hero): add CSS keyframes and new element styles"
```

---

## Task 2: Glyph pulse animation + boot sequence staggered lines

**Files:**
- Modify: `docs/index.html` — topbar glyph CSS (line ~136), hero boot HTML (lines 3269–3273)

- [ ] **Step 1: Add `glyphPulse` to `.mark .glyph`**

Find:
```css
  .mark .glyph{
    width:28px; height:28px;
    display:grid; place-items:center;
    font-weight: 700; font-size:13px;
    color: var(--bg);
    background: var(--amber);
    border-radius: 1px;
    box-shadow: 0 0 18px rgba(244,184,96,.4);
  }
```

Replace with:
```css
  .mark .glyph{
    width:28px; height:28px;
    display:grid; place-items:center;
    font-weight: 700; font-size:13px;
    color: var(--bg);
    background: var(--amber);
    border-radius: 1px;
    box-shadow: 0 0 18px rgba(244,184,96,.4);
    animation: glyphPulse 2.4s ease-in-out infinite;
  }
```

- [ ] **Step 2: Add `ctaGlow` to `.btn.primary`**

Find:
```css
  .btn.primary{
    background: var(--amber);
    color: var(--bg);
    border: 1px solid var(--amber);
    box-shadow: 0 4px 20px rgba(244,184,96,.25);
  }
```

Replace with:
```css
  .btn.primary{
    background: var(--amber);
    color: var(--bg);
    border: 1px solid var(--amber);
    box-shadow: 0 4px 20px rgba(244,184,96,.25);
    animation: ctaGlow 2.5s ease 3.5s infinite;
  }
```

- [ ] **Step 3: Wrap boot lines in `.line` divs**

Find:
```html
      <div class="boot">
        <div><span class="arrow">▸</span> <span class="info">bibops::init</span> <span class="ok">[ok]</span></div>
        <div><span class="arrow">▸</span> <span class="info">loading 21 tickets from </span><span class="ok">data/inputs/benchmark/</span></div>
        <div><span class="arrow">▸</span> <span class="info">judge model</span> <span class="ok">gpt-5.2</span> <span class="info">/ agent</span> <span class="ok">phi3:latest</span></div>
        <div><span class="arrow">▸</span> <span class="info">composite policy</span> <span class="ok">v1.0.0</span> <span class="info">ready</span><span class="blink"></span></div>
      </div>
```

Replace with:
```html
      <div class="boot">
        <div class="line"><span class="arrow">▸</span> <span class="info">bibops::init</span> <span class="ok">[ok]</span></div>
        <div class="line"><span class="arrow">▸</span> <span class="info">loading 21 tickets from </span><span class="ok">data/inputs/benchmark/</span></div>
        <div class="line"><span class="arrow">▸</span> <span class="info">judge model</span> <span class="ok">gpt-5.2</span> <span class="info">/ agent</span> <span class="ok">phi3:latest</span></div>
        <div class="line"><span class="arrow">▸</span> <span class="info">composite policy</span> <span class="ok">v1.0.0</span> <span class="info">ready</span><span class="blink"></span></div>
      </div>
```

- [ ] **Step 4: Verify in browser**

Reload `docs/index.html`. The four boot lines should stagger in (0.1s, 0.4s, 0.7s, 1.0s). The amber `BB` glyph in the topbar should slowly pulse its glow. The primary CTA button should start glowing ~3.5s after load.

- [ ] **Step 5: Commit**

```bash
git add docs/index.html
git commit -m "feat(hero): staggered boot sequence + glyph and CTA pulse animations"
```

---

## Task 3: Specs grid — 5 columns, counter IDs, sparkline column

**Files:**
- Modify: `docs/index.html` — `.hero .specs` CSS (line ~344), hero specs HTML (lines 3289–3306)

- [ ] **Step 1: Update specs grid CSS to 5 columns**

Find:
```css
  .hero .specs{
    margin: 44px 0 0;
    display: grid; grid-template-columns: repeat(4, 1fr);
    max-width: 800px;
    gap: 1px;
    background: var(--grid);
    border: 1px solid var(--grid);
  }
```

Replace with:
```css
  .hero .specs{
    margin: 44px 0 0;
    display: grid; grid-template-columns: repeat(4, 1fr) 160px;
    max-width: 1040px;
    gap: 1px;
    background: var(--grid);
    border: 1px solid var(--grid);
  }
```

- [ ] **Step 2: Replace specs grid HTML with counter IDs and sparkline column**

Find:
```html
      <div class="specs">
        <div>
          <div class="k">— tickets</div>
          <div class="v">21</div>
        </div>
        <div>
          <div class="k">— domaines</div>
          <div class="v">IT</div>
        </div>
        <div>
          <div class="k">— architectures</div>
          <div class="v">2</div>
        </div>
        <div>
          <div class="k">— dimensions</div>
          <div class="v">6</div>
        </div>
      </div>
```

Replace with:
```html
      <div class="specs">
        <div>
          <div class="k">— tickets évalués</div>
          <div class="v" id="hero-cnt-tickets">0</div>
        </div>
        <div>
          <div class="k">— composite · MA</div>
          <div class="v" id="hero-cnt-ma" style="color:var(--green)">0<span style="font-size:12px;color:var(--slate)">/100</span></div>
        </div>
        <div>
          <div class="k">— composite · LLM</div>
          <div class="v" id="hero-cnt-llm" style="color:var(--red)">0<span style="font-size:12px;color:var(--slate)">/100</span></div>
        </div>
        <div>
          <div class="k">— qualité MA</div>
          <div class="v" id="hero-cnt-q" style="color:var(--amber)">0<span style="font-size:12px;color:var(--slate)">/10</span></div>
        </div>
        <div class="spec-spark">
          <div class="k">Score · MA vs LLM</div>
          <div class="spark-labels"><span class="ma">▲ MA</span><span class="llm">▲ LLM</span></div>
          <svg viewBox="0 0 140 52" fill="none" style="width:100%;height:52px">
            <line x1="0" y1="13" x2="140" y2="13" stroke="#1E2A3A" stroke-width="1"/>
            <line x1="0" y1="26" x2="140" y2="26" stroke="#1E2A3A" stroke-width="1"/>
            <line x1="0" y1="39" x2="140" y2="39" stroke="#1E2A3A" stroke-width="1"/>
            <line x1="0" y1="20" x2="140" y2="20" stroke="#E8E2D5" stroke-width="0.7" stroke-dasharray="3 3" opacity="0.25"/>
            <polyline points="0,41 23,43 46,39 70,45 93,37 116,42 140,40" stroke="#6BB6CC" stroke-width="1.5" fill="none" stroke-linecap="round"/>
            <polygon points="0,17 23,15 46,13 70,19 93,11 116,14 140,12 140,52 0,52" fill="rgba(244,184,96,0.08)"/>
            <polyline points="0,17 23,15 46,13 70,19 93,11 116,14 140,12" stroke="#F4B860" stroke-width="1.8" fill="none" stroke-linecap="round"/>
            <text x="3" y="10" font-family="JetBrains Mono,monospace" font-size="7" fill="#F4B860">91.3</text>
            <text x="3" y="50" font-family="JetBrains Mono,monospace" font-size="7" fill="#6BB6CC">46.1</text>
          </svg>
        </div>
      </div>
```

- [ ] **Step 3: Verify layout in browser**

Reload the page. The specs grid should now show 5 columns — four metric cells and the sparkline on the right. The SVG lines should be visible (amber for MA high, cyan for LLM low, with a subtle amber fill).

- [ ] **Step 4: Commit**

```bash
git add docs/index.html
git commit -m "feat(hero): 5-column specs grid with sparkline column and counter IDs"
```

---

## Task 4: Live strip + score comparison cards + progress bar HTML

**Files:**
- Modify: `docs/index.html` — hero section, after specs grid closing `</div>` (line 3306), before `.actions` div (line 3308)

- [ ] **Step 1: Insert live strip + score cards + progress bar HTML**

Find:
```html
      <div class="actions">
        <a href="#bataille" class="btn primary">▸ view benchmark</a>
        <a href="#expedition" class="btn ghost">explore architecture</a>
      </div>
```

Replace with:
```html
      <div class="live-strip">
        <div class="lc"><div class="ld gr"></div><span class="lt">Eval Engine</span><span class="lv">online</span></div>
        <div class="lc"><div class="ld am"></div><span class="lt">RAG · ChromaDB</span><span class="lv">ready</span></div>
        <div class="lc"><div class="ld cy"></div><span class="lt">Racing Arena</span><span class="lv">4 teams</span></div>
        <div class="lc"><div class="ld mg"></div><span class="lt">A2A Probes</span><span class="lv">3 agents</span></div>
        <div class="lc" style="flex:1.4"><div class="ld gr"></div><span class="lt">Judge</span><span class="lv" style="font-size:10px">gpt-4o · 21 tickets</span></div>
      </div>

      <div class="hero-compare">
        <div class="hc-card ma">
          <div class="hc-arch">Architecture α</div>
          <div class="hc-name">Multi-Agents ReAct</div>
          <div class="hc-score">91.3<small>/100</small></div>
          <div class="hc-badge">✓ PASS</div>
          <div class="hc-bars">
            <div class="hc-bar-row">
              <div class="hb-k">Qualité</div>
              <div class="hb-track"><div class="hb-fill" style="width:78.6%"></div></div>
              <div class="hb-v">7.86</div>
            </div>
            <div class="hc-bar-row">
              <div class="hb-k">Sécurité</div>
              <div class="hb-track"><div class="hb-fill" style="width:99.7%"></div></div>
              <div class="hb-v">9.97</div>
            </div>
            <div class="hc-bar-row">
              <div class="hb-k">Composite</div>
              <div class="hb-track"><div class="hb-fill" style="width:91.3%"></div></div>
              <div class="hb-v">9.13</div>
            </div>
          </div>
        </div>

        <div class="hc-sep">
          <div class="vs">vs</div>
          <div class="delta">+45.2</div>
        </div>

        <div class="hc-card llm">
          <div class="hc-arch">Architecture β</div>
          <div class="hc-name">LLM Unique (zero-shot)</div>
          <div class="hc-score">46.1<small>/100</small></div>
          <div class="hc-badge">✗ FAIL</div>
          <div class="hc-bars">
            <div class="hc-bar-row">
              <div class="hb-k">Qualité</div>
              <div class="hb-track"><div class="hb-fill" style="width:28.1%"></div></div>
              <div class="hb-v">2.81</div>
            </div>
            <div class="hc-bar-row">
              <div class="hb-k">Sécurité</div>
              <div class="hb-track"><div class="hb-fill" style="width:99.7%"></div></div>
              <div class="hb-v">9.97</div>
            </div>
            <div class="hc-bar-row">
              <div class="hb-k">Composite</div>
              <div class="hb-track"><div class="hb-fill" style="width:46.1%"></div></div>
              <div class="hb-v">4.61</div>
            </div>
          </div>
        </div>
      </div>

      <div class="bench-status">
        <div class="bs-label">
          <span>Benchmark · 21 tickets</span>
          <span class="pass">20/21 qualité ≥7 · MA</span>
        </div>
        <div class="bs-track"><div class="bs-fill"></div></div>
        <div class="bs-segs">
          <span>Qualité ≥7</span>
          <span>Sécurité ≥6</span>
          <span>Validé ✓</span>
        </div>
      </div>

      <div class="actions">
        <a href="#bataille" class="btn primary">▸ view benchmark</a>
        <a href="#expedition" class="btn ghost">explore architecture</a>
      </div>
```

- [ ] **Step 2: Verify in browser**

Reload. Below the specs grid you should see:
- A 5-cell live status strip with colored pulsing dots
- Two score cards side by side (MA green 91.3 PASS, LLM red 46.1 FAIL) with bars that animate in ~2.7s
- A thin progress bar that fills to 95.2% (20/21) ~2.8s after load
- The original CTA buttons below

- [ ] **Step 3: Commit**

```bash
git add docs/index.html
git commit -m "feat(hero): live strip, score comparison cards, and benchmark progress bar"
```

---

## Task 5: JS — animated counters reading from #bibops-data

**Files:**
- Modify: `docs/index.html` — add `<script>` block before `</body>` (line 6316)

- [ ] **Step 1: Add counter animation script**

Find:
```html
</body>
```

Replace with:
```html
<script>
(function(){
  /* Hero counter animation — reads real values from embedded #bibops-data */
  var raw = document.getElementById('bibops-data');
  if (!raw) return;
  var d;
  try { d = JSON.parse(raw.textContent); } catch(e){ return; }

  var ma  = d.composite.architectures.systeme_multi_agents.composite_score; // 91.34
  var llm = d.composite.architectures.llm_unique.composite_score;           // 46.14
  var q   = d.summary.systeme_multi_agents.score_moyen;                     // 7.86
  var n   = d.diagnostics.ticket_count;                                      // 21

  function animNum(id, target, decimals, unit, delay) {
    setTimeout(function(){
      var el = document.getElementById(id);
      if (!el) return;
      var start = performance.now();
      var dur = 900;
      var unitHtml = unit ? '<span style="font-size:12px;color:var(--slate)">' + unit + '</span>' : '';
      (function step(now){
        var t = Math.min((now - start) / dur, 1);
        var ease = 1 - Math.pow(1 - t, 3);
        var val = (target * ease).toFixed(decimals);
        el.innerHTML = val + unitHtml;
        if (t < 1) requestAnimationFrame(step);
      })(start);
    }, delay);
  }

  animNum('hero-cnt-tickets', n,   0, '',     2200);
  animNum('hero-cnt-ma',      ma,  1, '/100', 2300);
  animNum('hero-cnt-llm',     llm, 1, '/100', 2400);
  animNum('hero-cnt-q',       q,   2, '/10',  2500);
})();
</script>

</body>
```

- [ ] **Step 2: Verify counters animate**

Reload `docs/index.html`. Starting ~2.2s after load, each spec value should count up from 0:
- Tickets: `0` → `21`
- MA composite: `0.0` → `91.3/100` (green)
- LLM composite: `0.0` → `46.1/100` (red)
- MA quality: `0.00` → `7.86/10` (amber)

- [ ] **Step 3: Verify data-driven (not hardcoded)**

In DevTools Console, run:
```js
JSON.parse(document.getElementById('bibops-data').textContent).composite.architectures.systeme_multi_agents.composite_score
```
Expected output: `91.34`. The counter should animate to that same value.

- [ ] **Step 4: Commit**

```bash
git add docs/index.html
git commit -m "feat(hero): data-driven counter animation from embedded bibops-data JSON"
```

---

## Task 6: Ticker enhancements

**Files:**
- Modify: `docs/index.html` — ticker CSS (line ~206), ticker HTML (line ~3243)

- [ ] **Step 1: Reduce ticker scroll duration from 60s to 50s**

Find:
```css
    animation: scroll-left 60s linear infinite;
```

Replace with:
```css
    animation: scroll-left 50s linear infinite;
```

- [ ] **Step 2: Add 3 new ticker entries**

Find:
```html
    <span>racing :: <b>team_b_react</b> wins defensive · detection <b>80%</b></span>
    <span>attacker :: <b>team_psi</b> · 5 extractions</span>
    <span class="sep">|</span>
    <span class="up">▸ all systems nominal</span>
    <span>—</span>
```

Replace with:
```html
    <span>racing :: <b>team_b_react</b> wins defensive · detection <b>80%</b></span>
    <span>attacker :: <b>team_psi</b> · 5 extractions</span>
    <span class="sep">|</span>
    <span>ragas :: iter-1→3 avg climb <span class="up">+2.1 pts</span></span>
    <span>a2a :: <b>agent-f</b> quality <span class="up">7.73</span> · security <span class="up">9.64</span></span>
    <span>co₂ :: MA <b>0.024 gCO₂e</b> · <span class="up">−63.8% vs LLM</span></span>
    <span class="sep">|</span>
    <span class="up">▸ all systems nominal</span>
    <span>—</span>
```

- [ ] **Step 3: Verify ticker**

Reload the page. The ticker should now include the RAGAS, A2A and CO₂ entries, and the scroll should feel slightly faster than before.

- [ ] **Step 4: Commit**

```bash
git add docs/index.html
git commit -m "feat(hero): enhanced ticker with RAGAS, A2A, and CO2 entries"
```

---

## Self-Review Checklist

### Spec coverage

| Spec item | Task |
|---|---|
| Glyph pulse animation | Task 2 Step 1 |
| Boot sequence staggered fade-in | Task 2 Step 3 |
| `heroFadeUp` cascade for all hero elements | Task 1 (CSS block) |
| Animated counters | Task 3 (counter IDs) + Task 5 (JS) |
| Sparkline column in specs grid | Task 3 Steps 1-2 |
| System live strip | Task 4 |
| Score comparison cards with animated bars | Task 4 |
| Benchmark progress bar | Task 4 |
| CTA glow ring | Task 2 Step 2 |
| Ticker enhancements | Task 6 |
| Data values read from `#bibops-data` | Task 5 Step 1 |
| Responsive: ≤840px collapse | Task 1 (media query) |

All spec items covered. ✓

### Type/naming consistency

- Counter IDs: `hero-cnt-tickets`, `hero-cnt-ma`, `hero-cnt-llm`, `hero-cnt-q` — used consistently in Task 3 HTML and Task 5 JS ✓
- CSS classes: `.live-strip`, `.hc-card`, `.hc-bar-row`, `.bench-status` — defined in Task 1, used in Task 4 HTML ✓
- Animation names: `glyphPulse`, `ctaGlow`, `bootIn`, `heroFadeUp`, `fillBar`, `fillIn` — all defined in Task 1 before use ✓
