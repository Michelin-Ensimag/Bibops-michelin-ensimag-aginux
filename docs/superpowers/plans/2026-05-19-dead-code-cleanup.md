# Dead Code Cleanup Refactoring Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce lines of code by removing dead functions/constants, deduplicating copy-pasted utilities, and collapsing near-identical files — without changing any observable logic.

**Architecture:** Eight independent, surgically scoped tasks. Each task is self-contained: remove dead code, move shared code to `src/common/`, or collapse a near-duplicate file into a thin re-export. Tests pass before and after each task.

**Tech Stack:** Python 3.11, pytest, standard `grep`/`wc -l` for verification.

---

## Before you start

Run the full test suite once to confirm a green baseline:

```bash
PYTHONPATH=. pytest tests/unit/ -q
```

Expected: all tests pass. Keep this terminal open to re-run after each task.

---

## Task 1 — Remove dead functions in `src/agent/`

**Scope:** Two functions with zero callers anywhere in `src/` or `tests/`.

**Files:**
- Modify: `src/agent/maestro.py` (remove ~70 lines at end of file)
- Modify: `src/agent/tools.py` (remove ~2 lines)

- [ ] **Step 1: Confirm there are no callers**

```bash
grep -rn "evaluer_agent_sur_tickets\|get_tool_policies" src/ tests/ | grep -v "def "
```

Expected: empty output.

- [ ] **Step 2: Remove `evaluer_agent_sur_tickets` from `maestro.py`**

Find the function at line ~894. It starts with:
```python
def evaluer_agent_sur_tickets(
```
Delete the entire function body until the next top-level `def` or end of file.

- [ ] **Step 3: Remove `get_tool_policies` from `tools.py`**

Find at line ~58:
```python
def get_tool_policies() -> dict[str, dict[str, Any]]:
    return {name: asdict(policy) for name, policy in TOOL_POLICIES.items()}
```
Delete both lines.

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=. pytest tests/unit/test_maestro.py tests/unit/test_outils.py -q
```

Expected: PASS. No output differences.

- [ ] **Step 5: Commit**

```bash
git add src/agent/maestro.py src/agent/tools.py
git commit -m "refactor: remove unused evaluer_agent_sur_tickets and get_tool_policies"
```

---

## Task 2 — Remove dead code in `src/bibops/benchmark/compare_a2a_agents.py`

**Scope:** Five dead symbols in the 2 633-line file. None are called from within the file or from any test.

**Files:**
- Modify: `src/bibops/benchmark/compare_a2a_agents.py`

- [ ] **Step 1: Confirm dead symbols have no callers**

```bash
grep -n "MODEL_SELF_REPORT_PROMPT\|SHA_PROBE_TEXT\|_normalize_quality\|_detect_capability\|_infer_use_case" \
  src/bibops/benchmark/compare_a2a_agents.py | grep -v "^[0-9]*:def \|^[0-9]*:MODEL_SELF_REPORT_PROMPT\s*=\|^[0-9]*:SHA_PROBE_TEXT\s*="
```

Expected: empty output (no call-sites, only definitions).

```bash
grep -rn "_detect_capability\|_infer_use_case\|_normalize_quality" tests/
```

Expected: empty output.

- [ ] **Step 2: Remove `MODEL_SELF_REPORT_PROMPT` constant (~line 175)**

Delete the 4-line block:
```python
MODEL_SELF_REPORT_PROMPT = (
    "Identify your underlying LLM if you can. Return only JSON with these keys: "
    "model_family, model_name, confidence, evidence. If you do not know, use UNKNOWN."
)
```

Note: `IDENTITY_SELF_REPORT_PROMPT` (line 180) and `KAGGLE_ANSWER_KEY` (line 188) are used — keep them.

- [ ] **Step 3: Remove `SHA_PROBE_TEXT` constant (~line 195)**

Delete:
```python
SHA_PROBE_TEXT = "BibOps OpenClaw MCP proof 2026-05-12"
```

- [ ] **Step 4: Remove `_normalize_quality` function (~line 551, 12 lines)**

Delete the entire function:
```python
def _normalize_quality(outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    quality = outputs.get("quality", {})
    try:
        score = float(quality.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    return {
        "status": str(quality.get("status", "skipped")),
        "score": round(clamp(score, 0.0, 10.0), 2),
        "justification": str(quality.get("justification", "")),
        "error": str(quality.get("error", "")),
    }
```

Note: `_normalize_security` (line 565) IS called — keep it.

- [ ] **Step 5: Remove `_detect_capability` function (~line 1014, 20 lines)**

Delete the entire function:
```python
def _detect_capability(
    expected_capability: str,
    answer: str,
    quality: dict[str, Any],
    security: dict[str, Any],
) -> tuple[bool, str]:
    """Backward-compatible detector used by older tests and ad-hoc imports."""
    expected = expected_capability.lower().strip()
    if expected in TOOL_CAPABILITIES:
        scored = _score_tool_capability(expected, answer)
        return bool(scored["detected"]), "; ".join(scored["evidence"])
    if expected == "security_refusal":
        scored = _score_security_probe({"id": "security"}, answer, security)
        return bool(scored["passed"]), "; ".join(scored["evidence"])
    role_probe = {"expected_capability": expected}
    role_score = _score_role_response(role_probe, answer, quality, security)
    if role_score:
        return role_score["score"] >= 6.0, f"role_score={role_score['score']:.2f}"
    score = float(quality.get("score", 0.0))
    return score >= 6.0, f"quality_score={score:.2f}"
```

- [ ] **Step 6: Remove `_infer_use_case` function (~line 1492, 2 lines)**

Delete:
```python
def _infer_use_case(probe_details: list[dict[str, Any]]) -> str:
    return _infer_role(None, probe_details)["predicted_role"]
```

- [ ] **Step 7: Run tests**

```bash
PYTHONPATH=. pytest tests/unit/ -q -k "a2a or runner"
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/bibops/benchmark/compare_a2a_agents.py
git commit -m "refactor: remove 5 dead symbols in compare_a2a_agents (~40 lines)"
```

---

## Task 3 — Remove dead constants in `src/bibops/evaluation/config.py`

**Scope:** `DATE_FORMAT` and `KNOWN_MODELS` are defined but never imported (only `WEIGHTS`, `FEEDBACK_SCORES`, `TIME_THRESHOLDS`, `TOKEN_THRESHOLDS` are imported by `rule_engine.py`).

**Files:**
- Modify: `src/bibops/evaluation/config.py`

- [ ] **Step 1: Confirm nothing imports DATE_FORMAT or KNOWN_MODELS**

```bash
grep -rn "DATE_FORMAT\|KNOWN_MODELS" src/ tests/
```

Expected: only lines within `config.py` itself (their definitions). No imports.

- [ ] **Step 2: Delete the two constants**

Remove these lines from `src/bibops/evaluation/config.py`:
```python
# Format de la colonne dateheure attendue
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Modèles connus (pour analyse)
KNOWN_MODELS = [
    "llama3.2:1b",
    "gpt-4",
    "gpt-3.5-turbo",
    "claude-3-opus",
    "mistral-7b",
]
```

- [ ] **Step 3: Run tests**

```bash
PYTHONPATH=. pytest tests/unit/test_rule_engine_v2.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/bibops/evaluation/config.py
git commit -m "refactor: remove unused DATE_FORMAT and KNOWN_MODELS from evaluation config"
```

---

## Task 4 — Extract duplicated binom functions to `math_utils.py`

**Scope:** `_binom_pmf()` and `binom_test_two_sided()` are copy-pasted verbatim in both `position_bias.py` and `position_bias_statements.py`. Extract to `src/common/math_utils.py` and import from there.

**Files:**
- Modify: `src/common/math_utils.py`
- Modify: `src/bibops/benchmark/position_bias.py`
- Modify: `src/bibops/benchmark/position_bias_statements.py`

- [ ] **Step 1: Add the shared functions to `math_utils.py`**

Append to the end of `src/common/math_utils.py`:
```python
import math as _math


def binom_pmf(n: int, k: int, p: float) -> float:
    """Binomial probability mass function P(X=k) under Binomial(n, p)."""
    return _math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_test_two_sided(k: int, n: int, p0: float = 0.5) -> float:
    """Exact two-sided binomial test p-value (no scipy dependency)."""
    if n <= 0:
        return 1.0
    p_obs = binom_pmf(n, k, p0)
    return min(1.0, sum(binom_pmf(n, i, p0) for i in range(n + 1) if binom_pmf(n, i, p0) <= p_obs + 1e-15))
```

- [ ] **Step 2: Update `position_bias.py`**

Replace the two local function definitions:
```python
def _binom_pmf(n: int, k: int, p: float) -> float:
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_test_two_sided(k: int, n: int, p0: float = 0.5) -> float:
    """Exact two-sided binomial test p-value (no scipy dependency)."""
    if n <= 0:
        return 1.0

    p_obs = _binom_pmf(n, k, p0)
    p_value = 0.0
    for i in range(n + 1):
        p_i = _binom_pmf(n, i, p0)
        if p_i <= p_obs + 1e-15:
            p_value += p_i
    return min(1.0, p_value)
```

With:
```python
from src.common.math_utils import binom_test_two_sided
```

Then remove the `import math` line if it's no longer used by anything else in that file.

```bash
grep -n "^import math" src/bibops/benchmark/position_bias.py
```

- [ ] **Step 3: Update `position_bias_statements.py`**

Replace the two local function definitions:
```python
def _binom_pmf(n: int, k: int, p: float) -> float:
    from math import comb
    return comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_test_two_sided(k: int, n: int, p0: float = 0.5) -> float:
    if n <= 0:
        return 1.0
    p_obs = _binom_pmf(n, k, p0)
    return min(1.0, sum(_binom_pmf(n, i, p0) for i in range(n + 1) if _binom_pmf(n, i, p0) <= p_obs + 1e-15))
```

With:
```python
from src.common.math_utils import binom_test_two_sided
```

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=. pytest tests/unit/ -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/common/math_utils.py src/bibops/benchmark/position_bias.py src/bibops/benchmark/position_bias_statements.py
git commit -m "refactor: deduplicate binom functions into math_utils"
```

---

## Task 5 — Centralize FinOps pricing constants

**Scope:** Two modules define the same `2.50 / 10.00` USD-per-million-token constants under different names. Centralize in `src/common/config.py`.

**Files:**
- Modify: `src/common/config.py`
- Modify: `src/bibops/benchmark/adversarial.py`
- Modify: `src/bibops/benchmark/compare_architectures.py`

- [ ] **Step 1: Add constants to `config.py`**

Append at the end of `src/common/config.py`:
```python
LLM_COST_INPUT_PER_1M_USD: float = 2.50
LLM_COST_OUTPUT_PER_1M_USD: float = 10.00
```

- [ ] **Step 2: Update `adversarial.py`**

Remove:
```python
# Tarification FinOps (USD / 1M tokens) — grille GPT-4o / Claude 3.5 Sonnet.
_PRIX_INPUT_PER_M_USD = 2.50
_PRIX_OUTPUT_PER_M_USD = 10.00
```

Add to the imports at the top of `adversarial.py`:
```python
from src.common.config import LLM_COST_INPUT_PER_1M_USD, LLM_COST_OUTPUT_PER_1M_USD
```

Update the usage in `_finops_summary` (~line 103):
```python
cost = pt / 1_000_000 * _PRIX_INPUT_PER_M_USD + ct / 1_000_000 * _PRIX_OUTPUT_PER_M_USD
```
becomes:
```python
cost = pt / 1_000_000 * LLM_COST_INPUT_PER_1M_USD + ct / 1_000_000 * LLM_COST_OUTPUT_PER_1M_USD
```

- [ ] **Step 3: Update `compare_architectures.py`**

Remove:
```python
# FinOps heuristic (USD / 1M tokens), aligned with existing llm_professor constants.
USD_INPUT_PER_1M_TOKENS = 2.50
USD_OUTPUT_PER_1M_TOKENS = 10.00
```

Add to the imports:
```python
from src.common.config import LLM_COST_INPUT_PER_1M_USD, LLM_COST_OUTPUT_PER_1M_USD
```

Update the `cost_usd` property in `ArchMetrics` (~line 76):
```python
return round(
    (self.prompt_tokens / 1_000_000.0) * USD_INPUT_PER_1M_TOKENS
    + (self.completion_tokens / 1_000_000.0) * USD_OUTPUT_PER_1M_TOKENS,
    6,
)
```
becomes:
```python
return round(
    (self.prompt_tokens / 1_000_000.0) * LLM_COST_INPUT_PER_1M_USD
    + (self.completion_tokens / 1_000_000.0) * LLM_COST_OUTPUT_PER_1M_USD,
    6,
)
```

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=. pytest tests/unit/test_runners_coverage.py tests/unit/test_runners_extras.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/common/config.py src/bibops/benchmark/adversarial.py src/bibops/benchmark/compare_architectures.py
git commit -m "refactor: centralize FinOps pricing constants in common/config"
```

---

## Task 6 — Remove duplicate `appeler_modele` from `ab_test_user.py`

**Scope:** `ab_test_user.py` defines its own `appeler_modele()` which duplicates the concept in `ab_test_llm.py`. Replace with a direct use of `get_copilot_client()` + inline call, or the `call_chat_model` abstraction.

**Files:**
- Modify: `src/bibops/benchmark/ab_test_user.py`

- [ ] **Step 1: Read the current function and its only two callers**

```bash
grep -n "appeler_modele" src/bibops/benchmark/ab_test_user.py
```

Expected output (3 lines: definition at ~59, calls at ~112–113).

- [ ] **Step 2: Inline the logic at call-sites and delete the function**

The function is:
```python
def appeler_modele(client: OpenAI, modele: str, contexte: str, ticket: str, retries: int) -> str:
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            reponse = client.chat.completions.create(
                model=modele,
                messages=[
                    {"role": "system", "content": contexte},
                    {"role": "user", "content": ticket},
                ],
                max_tokens=512,
                temperature=0,
            )
            return _extraire_texte(reponse.choices[0].message)
        except Exception as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(1.2 * attempt)

    return f"[ERREUR_MODELE {modele}] {last_error}"
```

Replace the two call-sites:
```python
rep_a_modele = appeler_modele(client, args.model_a, contexte, question, args.retries)
rep_b_modele = appeler_modele(client, args.model_b, contexte, question, args.retries)
```

With a local helper defined immediately above `main()`:
```python
def _call(modele: str, contexte: str, ticket: str, retries: int) -> str:
    client = get_copilot_client()
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            resp = client.chat.completions.create(
                model=modele,
                messages=[{"role": "system", "content": contexte}, {"role": "user", "content": ticket}],
                max_tokens=512,
                temperature=0,
            )
            return _extraire_texte(resp.choices[0].message)
        except Exception as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(1.2 * attempt)
    return f"[ERREUR_MODELE {modele}] {last_error}"
```

And update call-sites to:
```python
rep_a_modele = _call(args.model_a, contexte, question, args.retries)
rep_b_modele = _call(args.model_b, contexte, question, args.retries)
```

Then remove the `client = get_copilot_client()` that was called in `main()` (now inside `_call`).

This also removes the `OpenAI` import if it was only used as a type annotation in `appeler_modele`. Check:

```bash
grep -n "^from openai\|^import openai\|OpenAI" src/bibops/benchmark/ab_test_user.py
```

If `OpenAI` is no longer referenced, remove the import.

- [ ] **Step 3: Run tests**

```bash
PYTHONPATH=. pytest tests/unit/test_ab_test_llm.py -q
```

Expected: PASS (there may not be a dedicated test for ab_test_user since it's interactive — that's fine).

- [ ] **Step 4: Commit**

```bash
git add src/bibops/benchmark/ab_test_user.py
git commit -m "refactor: remove duplicate appeler_modele from ab_test_user"
```

---

## Task 7 — Collapse `team_validated/state_tools.py` into a thin re-export

**Scope:** `team_validated/state_tools.py` (43 lines) is an exact copy of `team_client/state_tools.py` with only the `TEAM_ID` string different. Collapse to a 5-line re-export.

**Files:**
- Rewrite: `src/racing/team_validated/state_tools.py`

- [ ] **Step 1: Confirm the only difference is TEAM_ID**

```bash
diff src/racing/team_client/state_tools.py src/racing/team_validated/state_tools.py
```

Expected: only differences are the docstring and `TEAM_ID = "team_alpha"` vs `TEAM_ID = "team_c_validated"`.

- [ ] **Step 2: Rewrite `team_validated/state_tools.py`**

Replace the entire file content with:
```python
"""Team C — State & Tools (identical contract to team_client, separate identity)."""
from src.racing.team_client.state_tools import HUB_BASE_URL, TeamState, ask_michelin_engineer

TEAM_ID = "team_c_validated"

__all__ = ["HUB_BASE_URL", "TEAM_ID", "TeamState", "ask_michelin_engineer"]
```

Note: `ask_michelin_engineer` uses `TEAM_ID` via module-level lookup in `team_client/state_tools.py`. The tool's JSON payload embeds `TEAM_ID` at call-time from `team_client.state_tools.TEAM_ID`. Since `team_validated/state_tools.py` re-exports its own `TEAM_ID = "team_c_validated"`, verify which module's `TEAM_ID` is used in the tool's POST body.

Read `team_client/state_tools.py` line ~60: `json={"team_id": TEAM_ID, "query": question}`. The `TEAM_ID` here resolves to `team_client.state_tools.TEAM_ID = "team_alpha"` — which means `team_validated/nodes.py` needs to patch this.

Check how `team_validated/nodes.py` imports state_tools:
```bash
grep -n "state_tools\|TEAM_ID\|ask_michelin" src/racing/team_validated/nodes.py
```

If `team_validated/nodes.py` imports `ask_michelin_engineer` from `team_client.nodes` (which already imports from `team_client.state_tools`), then the tool always uses `team_alpha` as team_id regardless. This is existing behavior — do NOT change it here; just collapse the file.

- [ ] **Step 3: Run tests**

```bash
PYTHONPATH=. pytest tests/unit/test_racing_nodes.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/racing/team_validated/state_tools.py
git commit -m "refactor: collapse team_validated/state_tools into thin re-export (43->5 lines)"
```

---

## Task 8 — Reduce repeated try/except float-coercion in `compare_architectures.py`

**Scope:** Lines 146–188 contain three identical `try: float(x) / except (TypeError, ValueError): 0.0` patterns. Extract a `_safe_float()` one-liner used already in `charts.py`, or inline via the existing `clamp` + `float` pattern.

**Files:**
- Modify: `src/bibops/benchmark/compare_architectures.py`

- [ ] **Step 1: Add `_safe_float` helper at the top of the module (after imports)**

After the existing imports/constants block, add:
```python
def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
```

- [ ] **Step 2: Replace the three repeated try/except blocks in `_evaluate_quality`**

Current code (~lines 146–157):
```python
def _evaluate_quality(
    evaluation_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Normalize quality output from registry results."""
    quality = evaluation_outputs.get("quality", {})
    raw_score = quality.get("score", 0.0)
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(10.0, score))

    return {
        "status": str(quality.get("status", "error")),
        "score": round(score, 2),
        "justification": str(quality.get("justification", "")),
        "error": str(quality.get("error", "")),
    }
```

Replace with:
```python
def _evaluate_quality(
    evaluation_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    quality = evaluation_outputs.get("quality", {})
    score = max(0.0, min(10.0, _safe_float(quality.get("score", 0.0))))
    return {
        "status": str(quality.get("status", "error")),
        "score": round(score, 2),
        "justification": str(quality.get("justification", "")),
        "error": str(quality.get("error", "")),
    }
```

- [ ] **Step 3: Replace the try/except blocks in `_evaluate_security`**

Current code (~lines 166–187):
```python
def _evaluate_security(
    evaluation_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Normalize security output from registry results."""
    security = evaluation_outputs.get("security", {})
    raw_score = security.get("security_score", 0.0)
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(10.0, score))

    risks = security.get("risks", {})
    if not isinstance(risks, dict):
        risks = {}
    default_risks = {
        "pii": 1.0,
        "prompt_injection": 1.0,
        "secrets": 1.0,
        "malicious_urls": 1.0,
        "no_refusal": 1.0,
        "toxicity": 1.0,
    }
    for key in default_risks:
        try:
            default_risks[key] = float(risks.get(key, default_risks[key]))
        except (TypeError, ValueError):
            pass

    findings = security.get("findings", [])
    if not isinstance(findings, list):
        findings = []

    return {
        "status": str(security.get("status", "error")),
        "profile": str(security.get("profile", "p0_llminspector_aligned")),
        "security_score": round(score, 2),
        "blocked": bool(security.get("blocked", False)),
        "risk_avg": round(float(security.get("risk_avg", 1.0)), 4),
        "risks": {k: round(max(0.0, min(1.0, v)), 4) for k, v in default_risks.items()},
        "findings": findings,
        "error": str(security.get("error", "")),
    }
```

Replace with:
```python
def _evaluate_security(
    evaluation_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    security = evaluation_outputs.get("security", {})
    score = max(0.0, min(10.0, _safe_float(security.get("security_score", 0.0))))
    risks = security.get("risks", {})
    if not isinstance(risks, dict):
        risks = {}
    risk_keys = ("pii", "prompt_injection", "secrets", "malicious_urls", "no_refusal", "toxicity")
    normalized_risks = {k: _safe_float(risks.get(k, 1.0), default=1.0) for k in risk_keys}
    findings = security.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    return {
        "status": str(security.get("status", "error")),
        "profile": str(security.get("profile", "p0_llminspector_aligned")),
        "security_score": round(score, 2),
        "blocked": bool(security.get("blocked", False)),
        "risk_avg": round(_safe_float(security.get("risk_avg", 1.0), default=1.0), 4),
        "risks": {k: round(max(0.0, min(1.0, v)), 4) for k, v in normalized_risks.items()},
        "findings": findings,
        "error": str(security.get("error", "")),
    }
```

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=. pytest tests/unit/test_runners_coverage.py tests/unit/test_runners_extras.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bibops/benchmark/compare_architectures.py
git commit -m "refactor: extract _safe_float helper, eliminate 3 duplicated try/except blocks"
```

---

## Final verification

- [ ] **Run the full unit test suite**

```bash
PYTHONPATH=. pytest tests/unit/ -q
```

Expected: all tests PASS, no regressions.

- [ ] **Check total line reduction**

```bash
wc -l src/agent/maestro.py src/agent/tools.py \
       src/bibops/benchmark/compare_a2a_agents.py \
       src/bibops/evaluation/config.py \
       src/common/math_utils.py \
       src/bibops/benchmark/position_bias.py \
       src/bibops/benchmark/position_bias_statements.py \
       src/common/config.py \
       src/bibops/benchmark/adversarial.py \
       src/bibops/benchmark/compare_architectures.py \
       src/bibops/benchmark/ab_test_user.py \
       src/racing/team_validated/state_tools.py
```

---

## Summary of expected reductions

| Task | File(s) | Approx. lines removed |
|------|---------|----------------------|
| 1 | `maestro.py`, `tools.py` | ~72 |
| 2 | `compare_a2a_agents.py` | ~40 |
| 3 | `evaluation/config.py` | ~10 |
| 4 | `position_bias.py`, `position_bias_statements.py` | ~25 |
| 5 | `adversarial.py`, `compare_architectures.py` | ~8 |
| 6 | `ab_test_user.py` | ~15 |
| 7 | `team_validated/state_tools.py` | ~38 |
| 8 | `compare_architectures.py` | ~20 |
| **Total** | | **~228 lines** |
