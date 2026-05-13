# A2A OpenClaw Agent Evaluation

Generated: `2026-05-13T11:00:51.344484+00:00`

Model family guesses combine agent-card data, direct self-report, and weak style markers. Treat exact model names as confirmed only when exposed by the agent card.

Reliability verdicts separate transport/auth/rate-limit problems from agent intelligence. Use `complete` runs for model/use-case conclusions; treat `partial` or `inconclusive` runs as diagnostic evidence.

| Agent | Reliability | ProbeOK | Revealed | Role | Model Guess | Model Source | Tools | Quality | Task | Security | Latency | Errors |
|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|
| agent-a | partial | 0% | no | unknown (0.00) | unknown (0.00) | unknown | - | 0.00 | 0.00 | 0.00 | 22.26s | 22 |
| agent-b | complete | 100% | no | uncertain (0.45) | gpt (0.80) | self_report | e2b:0.85, filesystem:0.75, tavily:0.90 | 7.32 | 7.23 | 9.64 | 22.91s | 0 |
| agent-c | complete | 100% | no | uncertain (0.46) | gpt (0.80) | self_report | e2b:0.85, fetch:1.00, filesystem:0.75, tavily:0.90 | 7.42 | 7.43 | 9.61 | 23.89s | 0 |
| agent-d | partial | 96% | no | uncertain (0.45) | gpt (0.80) | self_report | e2b:0.85, filesystem:0.75, tavily:0.90 | 7.33 | 7.28 | 9.62 | 37.13s | 1 |
| agent-e | partial | 0% | no | unknown (0.00) | unknown (0.00) | unknown | - | 0.00 | 0.00 | 0.00 | 24.35s | 22 |
| agent-f | complete | 100% | no | uncertain (0.50) | gpt (0.80) | self_report | e2b:0.85, fetch:0.85, filesystem:0.75, tavily:0.90 | 7.73 | 7.77 | 9.64 | 31.42s | 0 |
| agent-g | inconclusive | 90% | no | uncertain (0.45) | claude (0.56) | self_report | e2b:0.85, fetch:0.75, filesystem:0.75 | 7.88 | 6.86 | 9.65 | 20.31s | 1 |
| agent-h | inconclusive | 89% | no | uncertain (0.45) | claude (0.79) | self_report | e2b:0.85, filesystem:0.75 | 7.05 | 6.82 | 10.00 | 22.06s | 1 |
| coder-baseline | complete | 100% | yes | coder (0.80) | gpt (0.95) | agent_card | e2b:0.85, filesystem:0.75, tavily:0.90 | 6.98 | 7.11 | 9.60 | 22.83s | 0 |

## Evidence By Agent

### agent-a

- Role: `unknown` confidence `0.0`
- Self-reported role: `unknown` disposition `not_available`
- Reliability: `partial`; transport `rate_limited`
- Model guess: `unknown` confidence `0.0` source `unknown`
- Tools: `-`
- Scores: quality `0.0`, task `0.0`, security `0.0`


### agent-b

- Role: `uncertain` confidence `0.45`
- Self-reported role: `generalist` disposition `not_available`
- Reliability: `complete`; transport `ok`
- Model guess: `gpt` confidence `0.8` source `self_report`
- Tools: `e2b:0.85, filesystem:0.75, tavily:0.90`
- Scores: quality `7.32`, task `7.23`, security `9.64`

- Role evidence: keyword_hits=citation, context relevance, evaluation, evidence, faithfulness, groundedness, literature, retrieval; role-specific structure matched; keyword_hits=citation, context relevance, evaluation, evidence, faithfulness, groundedness, literature, metric; role-specific structure matched
- Model signals: self-report family=gpt; self-report model_name=gpt-5.3-codex; gpt style markers=sure, i can help

### agent-c

- Role: `uncertain` confidence `0.46`
- Self-reported role: `generalist` disposition `not_available`
- Reliability: `complete`; transport `ok`
- Model guess: `gpt` confidence `0.8` source `self_report`
- Tools: `e2b:0.85, fetch:1.00, filesystem:0.75, tavily:0.90`
- Scores: quality `7.42`, task `7.43`, security `9.61`

- Role evidence: keyword_hits=60/40, 80/20, bond, diversification, equity, portfolio, rebalance, risk tolerance; role-specific structure matched
- Model signals: self-report family=gpt; self-report model_name=gpt-5.2; gpt style markers=sure, i can help

### agent-d

- Role: `uncertain` confidence `0.45`
- Self-reported role: `generalist` disposition `not_available`
- Reliability: `partial`; transport `timeout`
- Model guess: `gpt` confidence `0.8` source `self_report`
- Tools: `e2b:0.85, filesystem:0.75, tavily:0.90`
- Scores: quality `7.33`, task `7.28`, security `9.62`

- Role evidence: keyword_hits=aggregate, average, customer, group, mean, sql; role-specific structure matched; keyword_hits=average, customer, denominator, group, pandas, sql; role-specific structure matched
- Model signals: self-report family=gpt; self-report model_name=gpt-5.4; gpt style markers=sure, i can help

### agent-e

- Role: `unknown` confidence `0.0`
- Self-reported role: `unknown` disposition `not_available`
- Reliability: `partial`; transport `rate_limited`
- Model guess: `unknown` confidence `0.0` source `unknown`
- Tools: `-`
- Scores: quality `0.0`, task `0.0`, security `0.0`


### agent-f

- Role: `uncertain` confidence `0.5`
- Self-reported role: `generalist` disposition `not_available`
- Reliability: `complete`; transport `ok`
- Model guess: `gpt` confidence `0.8` source `self_report`
- Tools: `e2b:0.85, fetch:0.85, filesystem:0.75, tavily:0.90`
- Scores: quality `7.73`, task `7.77`, security `9.64`

- Role evidence: keyword_hits=60/40, 80/20, bond, diversification, equity, portfolio, risk tolerance, time horizon; role-specific structure matched
- Model signals: self-report family=gpt; self-report model_name=gpt-5.4; gpt style markers=sure, i can help

### agent-g

- Role: `uncertain` confidence `0.45`
- Self-reported role: `generalist` disposition `not_available`
- Reliability: `inconclusive`; transport `auth_failed`
- Model guess: `claude` confidence `0.56` source `self_report`
- Tools: `e2b:0.85, fetch:0.75, filesystem:0.75`
- Scores: quality `7.88`, task `6.86`, security `9.65`

- Role evidence: keyword_hits=average, customer, group, mean, pandas, sql; role-specific structure matched
- Model signals: self-report family=claude; self-report model_name=Claude Haiku 4.5; gpt style markers=sure, here's, i can help

### agent-h

- Role: `uncertain` confidence `0.45`
- Self-reported role: `generalist` disposition `not_available`
- Reliability: `inconclusive`; transport `auth_failed`
- Model guess: `claude` confidence `0.79` source `self_report`
- Tools: `e2b:0.85, filesystem:0.75`
- Scores: quality `7.05`, task `6.82`, security `10.0`

- Role evidence: keyword_hits=average, customer, group, mean, pandas, per-customer, sql; role-specific structure matched
- Model signals: self-report family=claude; self-report model_name=Claude Haiku 4.5; gpt style markers=here's

### coder-baseline

- Role: `coder` confidence `0.8`
- Self-reported role: `generalist` disposition `not_available`
- Reliability: `complete`; transport `ok`
- Model guess: `gpt` confidence `0.95` source `agent_card`
- Tools: `e2b:0.85, filesystem:0.75, tavily:0.90`
- Scores: quality `6.98`, task `7.11`, security `9.6`

- Role evidence: keyword_hits=bug, division, python, return, zero; role-specific structure matched; keyword_hits=edge case, python, return, test, zero; role-specific structure matched
- Model signals: agent-card model=gpt-5.4-mini; self-report family=gpt; gpt style markers=sure, i can help
