"""
outils.py — LangChain tools used by lang-gen.py.

A "tool" is just a Python function decorated with @tool so LangChain agents
can discover it, call it automatically, and read its return value.
This file defines one tool: fetch_python_whatsnew, which scrapes the official
Python docs to get a summary of the latest release highlights.
"""

from __future__ import annotations

import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool  # langchain_core, not langchain (removed in 1.x)

# ---------------------------------------------------------------------------
# STEP 1 — Base URL
# The Python docs publish a "What's New" index page listing every release.
# We start here to discover the URL for the latest version automatically.
# ---------------------------------------------------------------------------
BASE_URL = "https://docs.python.org/3/whatsnew/"


# ---------------------------------------------------------------------------
# STEP 2 — HTTP helper
# A thin wrapper around httpx so all requests share the same timeout and
# User-Agent header. Using a context manager ensures the connection is closed.
# ---------------------------------------------------------------------------
def _fetch(url: str, timeout: float = 20.0) -> str:
    with httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": "BibOps-RAG-Demo/1.0"},
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


# ---------------------------------------------------------------------------
# STEP 3 — Find the latest "What's New" entry
# We parse the index page, collect all links that match
# "What's New In Python 3.x", and return the one with the highest minor version.
# ---------------------------------------------------------------------------
def _find_latest_url(index_html: str) -> Optional[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    candidates = []
    for a_tag in soup.find_all("a"):
        text = (a_tag.get_text() or "").strip()
        href = a_tag.get("href")
        if text.lower().startswith("what's new in python 3") and href:
            url = href if href.startswith("http") else BASE_URL + href
            m = re.search(r"3\.(\d+)", text)
            minor = int(m.group(1)) if m else -1
            candidates.append((minor, url))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


# ---------------------------------------------------------------------------
# STEP 4 — Extract the interesting sections from the article
# We strip navigation chrome, then walk each h2 section.
# Housekeeping sections (credits, deprecations…) are skipped — they're noise
# for a marketing newsletter. Each kept section is capped at ~1600 chars so
# the combined output stays within the LLM's context window.
# ---------------------------------------------------------------------------
def _extract_highlights(article_html: str, max_chars: int = 8000) -> str:
    soup = BeautifulSoup(article_html, "html.parser")
    for tag in soup.select("nav, header, footer, aside"):
        tag.decompose()
    main = soup.select_one("main") or soup

    lines: list[str] = []
    title = main.find("h1") or soup.find("title")
    if title:
        lines.append(f"TITLE: {title.get_text(strip=True)}")

    skip_keywords = {"acknowledgements", "credits", "porting", "deprecated",
                     "removed", "documentation", "security", "contributors"}

    for h2 in main.find_all("h2"):
        section_title = h2.get_text(strip=True)
        if any(k in section_title.lower() for k in skip_keywords):
            continue
        content_parts = []
        for sib in h2.find_all_next():
            if sib.name == "h2":
                break
            if sib.name in {"p", "ul", "ol"}:
                text = sib.get_text(" ", strip=True)
                if text:
                    content_parts.append(text)
            if len("\n".join(content_parts)) > 1600:
                break
        if content_parts:
            lines.append(f"\n## {section_title}\n" + "\n".join(content_parts))

    extracted = "\n".join(lines)
    if len(extracted) > max_chars:
        extracted = extracted[:max_chars] + "\n...[truncated]"
    return extracted


# ---------------------------------------------------------------------------
# STEP 5 — The tool itself
# @tool turns this function into a LangChain tool. The agent sees the function
# name and docstring, decides when to call it, and receives the return value
# as an "observation" to reason over before composing its final answer.
# ---------------------------------------------------------------------------
@tool
def fetch_python_whatsnew() -> str:
    """
    Fetch the latest 'What's New in Python' article from the official docs and
    return a concise text summary including the URL and section highlights.
    """
    index_html = _fetch(BASE_URL)
    latest_url = _find_latest_url(index_html)
    if not latest_url:
        return "Could not determine the latest 'What's New' URL from the index page."
    article_html = _fetch(latest_url)
    highlights = _extract_highlights(article_html)
    return f"URL: {latest_url}\n\n{highlights}"
