"""
lang-gen.py — A LangChain agent that drafts a Python release newsletter.

Architecture:
  1. fetch_python_whatsnew (defined in tools.py) scrapes the official Python docs.
  2. create_agent() builds a ReAct loop: the agent fetches the page, reads it,
     then writes a structured marketing newsletter in one shot.
  3. ModelFallbackMiddleware retries with phi3 if mistral fails.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain_ollama import ChatOllama

# ---------------------------------------------------------------------------
# STEP 1 — Import the tool
# tools.py lives in the same directory, so a plain (non-relative) import works
# when running as a script. Relative imports (from .tools) only work inside a
# package and would break with `python lang-gen.py`.
# ---------------------------------------------------------------------------
from tools import fetch_python_whatsnew

# ---------------------------------------------------------------------------
# STEP 2 — Models
# Primary: mistral is more capable for long-form writing.
# Fallback: phi3 is lighter — used automatically if mistral fails.
# ---------------------------------------------------------------------------
llm = ChatOllama(model="mistral:latest", temperature=0)
llm_secours = ChatOllama(model="phi3:latest", temperature=0)

# ---------------------------------------------------------------------------
# STEP 3 — System prompt
# This is the "job description" we give the LLM. It tells the agent *what role
# to play* and *what structure to follow* for its output.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a senior Product Marketing Manager at the Python Software Foundation. "
    "Task: Draft a clear, engaging release marketing newsletter for end users and developers, "
    "highlighting the most compelling new features, performance improvements, and quality-of-life "
    "changes in the latest Python release.\n\n"
    "Process: Use the tool to fetch the latest 'What's New in Python' page. Read the highlights "
    "and craft a concise newsletter with: (1) an attention-grabbing subject line, "
    "(2) a short intro paragraph, (3) 4–8 bullet points of key features with user benefits, "
    "(4) short code snippets only if they add clarity, (5) a 'How to upgrade' section, "
    "and (6) links to official docs/changelog. Keep it accurate and avoid speculation."
)

# ---------------------------------------------------------------------------
# STEP 4 — Agent
# create_agent() wraps the LLM + tools in a LangGraph ReAct loop.
# The loop repeats: Think → Pick tool → Call tool → Observe → until done.
# ModelFallbackMiddleware transparently retries with llm_secours on errors.
# ---------------------------------------------------------------------------
agent = create_agent(
    model=llm,
    tools=[fetch_python_whatsnew],
    system_prompt=SYSTEM_PROMPT,
    middleware=[ModelFallbackMiddleware(llm_secours)],
)


# ---------------------------------------------------------------------------
# STEP 5 — Runner function
# Encapsulating the invoke() call in a function makes this file importable
# from other modules (e.g. a web server or a test) without executing anything.
# ---------------------------------------------------------------------------
def run_newsletter() -> str:
    user_message = (
        "Use the tool to fetch the latest 'What's New in Python' "
        "and then write the release marketing newsletter."
    )
    result = agent.invoke({"messages": [{"role": "user", "content": user_message}]})
    # agent.invoke() returns a LangGraph state dict; the final AI reply is the last message.
    return result["messages"][-1].content


# ---------------------------------------------------------------------------
# STEP 6 — CLI entry point
# Kept in __main__ so the agent is importable without side-effects.
# Usage: python lang-gen.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(run_newsletter())
