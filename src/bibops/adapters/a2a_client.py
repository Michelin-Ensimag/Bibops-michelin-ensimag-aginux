"""A2A client utilities for evaluating external agents with BibOps."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin

import requests
import requests.auth
from requests.auth import HTTPBasicAuth


class A2AClientError(RuntimeError):
    """Raised when discovery or JSON-RPC communication fails."""


@dataclass
class A2AAgentInfo:
    """Normalized metadata extracted from an A2A agent card."""

    base_url: str
    card_url: str
    rpc_url: str
    protocol_variant: str
    name: str
    description: str
    model: str | None
    skills: list[str]
    capabilities: dict[str, Any]
    revealed: bool
    raw_card: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class A2AAgentResult:
    """Normalized response from one A2A agent call."""

    agent_url: str
    agent_name: str
    prompt: str
    answer: str
    latency_s: float
    raw_response: dict[str, Any]
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class A2AStreamResult:
    """Normalized response from one A2A streaming call."""

    agent_url: str
    agent_name: str
    prompt: str
    answer: str
    latency_s: float
    events: list[dict[str, Any]]
    raw_lines: list[str]
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean_base_url(base_url: str) -> str:
    cleaned = (base_url or "").strip()
    if not cleaned:
        raise ValueError("base_url cannot be empty")
    return cleaned.rstrip("/")


def _card_candidates(base_url: str) -> list[tuple[str, str]]:
    base = _clean_base_url(base_url)
    return [
        ("openclaw", f"{base}/.well-known/agent-card.json"),
        ("fact_checker", f"{base}/.well-known/agent.json"),
    ]


def _fetch_json(url: str, timeout_s: int) -> dict[str, Any]:
    response = requests.get(url, timeout=timeout_s)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise A2AClientError(f"Agent card is not a JSON object: {url}")
    return payload


def _find_first_key(payload: Any, names: set[str]) -> Any:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in names and value not in ("", None):
                return value
        for value in payload.values():
            found = _find_first_key(value, names)
            if found not in ("", None):
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _find_first_key(item, names)
            if found not in ("", None):
                return found
    return None


def _extract_skills(card: dict[str, Any]) -> list[str]:
    raw_skills = card.get("skills") or card.get("capabilities", {}).get("skills") or []
    skills: list[str] = []
    if isinstance(raw_skills, list):
        for item in raw_skills:
            if isinstance(item, dict):
                label = item.get("id") or item.get("name") or item.get("title")
                if not label:
                    label = str(item.get("description", ""))[:80]
                if label:
                    skills.append(str(label))
            elif item:
                skills.append(str(item))
    return skills


def _extract_capabilities(card: dict[str, Any]) -> dict[str, Any]:
    caps = card.get("capabilities")
    return caps if isinstance(caps, dict) else {}


def _is_revealed(model: str | None, skills: list[str], card: dict[str, Any]) -> bool:
    if model:
        return True
    generic_skill_names = {"chat", "generic chat", "conversation"}
    normalized_skills = {skill.strip().lower() for skill in skills}
    if normalized_skills and not normalized_skills.issubset(generic_skill_names):
        return True
    raw = json.dumps(card, ensure_ascii=False).lower()
    return any(marker in raw for marker in ("claude", "gpt-", "gemini", "tavily", "e2b", "filesystem"))


def _resolve_rpc_url(base_url: str, card_url: str, card: dict[str, Any], variant: str) -> str:
    advertised = card.get("url") or card.get("endpoint") or card.get("rpcUrl")
    if isinstance(advertised, str) and advertised.strip():
        advertised = advertised.strip()
        if advertised.startswith("http://") or advertised.startswith("https://"):
            return advertised
        return urljoin(_clean_base_url(base_url) + "/", advertised.lstrip("/"))

    base = _clean_base_url(base_url)
    if variant == "openclaw" or "agent-card.json" in card_url:
        return f"{base}/a2a/jsonrpc"
    return f"{base}/"


def discover_agent(base_url: str, timeout_s: int = 30) -> A2AAgentInfo:
    """Fetch the A2A agent card and normalize metadata."""
    errors: list[str] = []
    for variant, card_url in _card_candidates(base_url):
        try:
            card = _fetch_json(card_url, timeout_s=timeout_s)
            rpc_url = _resolve_rpc_url(base_url, card_url, card, variant)
            name = str(card.get("name") or card.get("id") or _clean_base_url(base_url))
            description = str(card.get("description") or "")
            model_raw = _find_first_key(card, {"model", "modelname", "llm", "modelid"})
            model = str(model_raw) if model_raw not in ("", None) else None
            skills = _extract_skills(card)
            capabilities = _extract_capabilities(card)
            return A2AAgentInfo(
                base_url=_clean_base_url(base_url),
                card_url=card_url,
                rpc_url=rpc_url,
                protocol_variant=variant,
                name=name,
                description=description,
                model=model,
                skills=skills,
                capabilities=capabilities,
                revealed=_is_revealed(model, skills, card),
                raw_card=card,
            )
        except Exception as exc:
            errors.append(f"{card_url}: {exc}")
            continue

    raise A2AClientError("A2A discovery failed: " + " | ".join(errors))


def _message_parts(prompt: str, protocol_variant: str) -> list[dict[str, str]]:
    if protocol_variant == "openclaw":
        return [{"kind": "text", "text": prompt}]
    return [{"text": prompt}]


def _extract_text_from_part(part: Any) -> str:
    if isinstance(part, dict):
        text = part.get("text")
        if isinstance(text, str):
            return text
    return ""


def extract_text_from_response(payload: dict[str, Any]) -> str:
    """Extract text from common A2A JSON-RPC response shapes."""
    result = payload.get("result")
    if not isinstance(result, dict):
        return ""

    candidates: list[Any] = [
        result.get("parts"),
        result.get("message", {}).get("parts") if isinstance(result.get("message"), dict) else None,
        result.get("status", {}).get("message", {}).get("parts")
        if isinstance(result.get("status"), dict)
        and isinstance(result.get("status", {}).get("message"), dict)
        else None,
    ]

    artifacts = result.get("artifacts")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, dict):
                candidates.append(artifact.get("parts"))

    texts: list[str] = []
    for parts in candidates:
        if not isinstance(parts, list):
            continue
        for part in parts:
            text = _extract_text_from_part(part)
            if text.strip():
                texts.append(text.strip())

    if texts:
        return "\n\n".join(texts).strip()

    # Last-resort fallback keeps debugging information without crashing the benchmark.
    return json.dumps(result, ensure_ascii=False)[:4000]


_FACTCHECKER_A2A_URL = "https://a2a.emottet.com/"

_VERDICT_KEYWORDS = {
    "accurate":       1.0,
    "correct":        1.0,
    "vrai":           1.0,
    "juste":          1.0,
    "exact":          1.0,
    "fiable":         1.0,
    "valide":         1.0,
    "not accurate":   0.0,
    "incorrect":      0.0,
    "faux":           0.0,
    "erron":          0.0,
    "inexact":        0.0,
    "non correct":    0.0,
    "not applicable": 0.5,
    "non applicable": 0.5,
    "probable":       0.5,
    "incertain":      0.5,
}


class A2AFactChecker:
    """
    Sends an agent answer to an external A2A fact-checking oracle and parses
    back a numeric accuracy score (0.0 – 1.0).

    The factchecker at `a2a_url` reads the answer text, verifies its claims
    against public sources, and returns a structured verdict
    (Accurate / Not Accurate / Partially Accurate / Not Applicable).

    Credentials are read from fact-checker-specific env vars first, then the
    generic A2A env vars for backward compatibility — no default password.

    Usage:
        checker = A2AFactChecker()
        result  = checker.check_answer("Essayez de redémarrer Cisco AnyConnect.")
        print(result["accuracy_score_10"])   # 0.0 – 10.0
    """

    def __init__(
        self,
        a2a_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_s: int = 60,
    ):
        self.a2a_url = (a2a_url or os.environ.get("A2A_FACTCHECKER_URL", _FACTCHECKER_A2A_URL)).rstrip("/") + "/"
        self.username = username or os.environ.get("A2A_FACTCHECKER_USERNAME") or os.environ.get("A2A_USERNAME") or ""
        self.password = password or os.environ.get("A2A_FACTCHECKER_PASSWORD") or os.environ.get("A2A_PASSWORD") or ""
        self.timeout_s = timeout_s

    def _build_payload(self, answer_text: str, message_id: str = "fact-check-1") -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": message_id,
                    "parts": [{"text": answer_text}],
                }
            },
        }

    def _extract_text(self, payload: Any) -> str:
        """Walk common A2A response shapes to extract readable text."""
        if isinstance(payload, dict):
            for key in ("parts", "artifacts"):
                val = payload.get(key)
                if isinstance(val, list) and val:
                    texts = []
                    for item in val:
                        if isinstance(item, dict):
                            if "text" in item:
                                texts.append(str(item["text"]))
                            if "parts" in item:
                                texts.append(self._extract_text({"parts": item["parts"]}))
                    if texts:
                        return "\n".join(texts)
            for key in ("message", "response", "result", "status"):
                val = payload.get(key)
                if val is not None:
                    result = self._extract_text(val)
                    if result:
                        return result
        if isinstance(payload, list) and payload:
            return self._extract_text(payload[0])
        return str(payload or "")

    def _parse_accuracy(self, text: str) -> float | None:
        """Convert free-text verdict into a 0.0 – 1.0 score."""
        normalized = text.strip().lower()
        if not normalized:
            return None

        percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", normalized)
        if percent_match:
            return min(1.0, max(0.0, float(percent_match.group(1)) / 100.0))

        slash_match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", normalized)
        if slash_match:
            return min(1.0, max(0.0, float(slash_match.group(1)) / 10.0))

        score_match = re.search(
            r"(?:score|note|accuracy|exactitude)\s*[:=]?\s*(\d+(?:\.\d+)?)", normalized
        )
        if score_match:
            value = float(score_match.group(1))
            return min(1.0, max(0.0, value / 10.0 if value > 1.0 else value))

        # Multi-word keywords before single-word ones to avoid partial matches.
        for keyword, score in sorted(_VERDICT_KEYWORDS.items(), key=lambda kv: -len(kv[0])):
            if keyword in normalized:
                return score

        return None

    def check_answer(
        self,
        answer_text: str,
        message_id: str = "fact-check-1",
    ) -> dict[str, Any]:
        """
        Send `answer_text` to the fact-checking oracle and return a result dict:
            raw_response     – full JSON from the A2A agent
            parsed_text      – human-readable verdict text
            accuracy_score   – float 0.0-1.0, or None if unparseable
            accuracy_score_10 – float 0.0-10.0, or None
        """
        payload = self._build_payload(answer_text, message_id)
        auth = requests.auth.HTTPBasicAuth(self.username, self.password) if self.username else None
        response = requests.post(
            self.a2a_url,
            json=payload,
            auth=auth,
            headers={"Content-Type": "application/json"},
            timeout=self.timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        result_payload = data.get("result") or data
        text = self._extract_text(result_payload)
        accuracy = self._parse_accuracy(text)
        return {
            "raw_response": data,
            "parsed_text": text,
            "accuracy_score": accuracy,
            "accuracy_score_10": round(accuracy * 10, 2) if accuracy is not None else None,
        }


def send_message(
    agent: A2AAgentInfo,
    prompt: str,
    username: str | None = None,
    password: str | None = None,
    timeout_s: int = 120,
    method: str = "message/send",
) -> A2AAgentResult:
    """Send one JSON-RPC message to an A2A agent and normalize the answer."""
    message_id = f"bibops-{uuid.uuid4()}"
    payload = {
        "jsonrpc": "2.0",
        "id": message_id,
        "method": method,
        "params": {
            "message": {
                "role": "user",
                "messageId": message_id,
                "parts": _message_parts(prompt, agent.protocol_variant),
            }
        },
    }

    auth = HTTPBasicAuth(username, password) if username and password else None
    start = time.perf_counter()
    try:
        response = requests.post(
            agent.rpc_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            auth=auth,
            timeout=timeout_s,
        )
        latency_s = time.perf_counter() - start
        response.raise_for_status()
        raw_response = response.json()
        if not isinstance(raw_response, dict):
            raise A2AClientError("JSON-RPC response is not an object")
        answer = extract_text_from_response(raw_response)
        return A2AAgentResult(
            agent_url=agent.base_url,
            agent_name=agent.name,
            prompt=prompt,
            answer=answer,
            latency_s=round(latency_s, 4),
            raw_response=raw_response,
        )
    except Exception as exc:
        latency_s = time.perf_counter() - start
        return A2AAgentResult(
            agent_url=agent.base_url,
            agent_name=agent.name,
            prompt=prompt,
            answer="",
            latency_s=round(latency_s, 4),
            raw_response={},
            error=str(exc),
        )


def _decode_sse_data_lines(lines: list[str]) -> list[dict[str, Any]]:
    """Parse best-effort JSON payloads from SSE `data:` lines."""
    events: list[dict[str, Any]] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if not data or data == "[DONE]":
            continue
        try:
            payload = json.loads(data)
            if isinstance(payload, dict):
                events.append(payload)
            else:
                events.append({"data": payload})
        except json.JSONDecodeError:
            events.append({"text": data})
    return events


def _extract_text_from_stream_events(events: list[dict[str, Any]]) -> str:
    """Collect human-readable text from common A2A stream event shapes."""
    texts: list[str] = []
    for event in events:
        text = extract_text_from_response(event)
        if text.strip():
            texts.append(text.strip())
            continue

        result = event.get("result")
        if isinstance(result, dict):
            text = extract_text_from_response({"result": result})
            if text.strip():
                texts.append(text.strip())
                continue

        for key in ("text", "delta", "content"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                texts.append(value.strip())
                break
    return "\n\n".join(dict.fromkeys(texts)).strip()


def send_stream_message(
    agent: A2AAgentInfo,
    prompt: str,
    username: str | None = None,
    password: str | None = None,
    timeout_s: int = 120,
) -> A2AStreamResult:
    """
    Send one A2A `message/stream` request and collect SSE events.

    OpenClaw may expose intermediate tool activity through stream events. The
    parser is intentionally permissive because A2A implementations differ in
    event envelope shape.
    """
    message_id = f"bibops-stream-{uuid.uuid4()}"
    payload = {
        "jsonrpc": "2.0",
        "id": message_id,
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": message_id,
                "parts": _message_parts(prompt, agent.protocol_variant),
            }
        },
    }

    auth = HTTPBasicAuth(username, password) if username and password else None
    start = time.perf_counter()
    raw_lines: list[str] = []
    try:
        with requests.post(
            agent.rpc_url,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            auth=auth,
            timeout=timeout_s,
            stream=True,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                if line is not None:
                    raw_lines.append(str(line))

        latency_s = time.perf_counter() - start
        events = _decode_sse_data_lines(raw_lines)
        answer = _extract_text_from_stream_events(events)
        return A2AStreamResult(
            agent_url=agent.base_url,
            agent_name=agent.name,
            prompt=prompt,
            answer=answer,
            latency_s=round(latency_s, 4),
            events=events,
            raw_lines=raw_lines,
        )
    except Exception as exc:
        latency_s = time.perf_counter() - start
        return A2AStreamResult(
            agent_url=agent.base_url,
            agent_name=agent.name,
            prompt=prompt,
            answer="",
            latency_s=round(latency_s, 4),
            events=[],
            raw_lines=raw_lines,
            error=str(exc),
        )
