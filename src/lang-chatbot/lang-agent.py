"""
lang-agent.py — A LangChain agent with a RAG tool and model fallback.

Architecture:
  1. A Chroma vector store (built by main.py) holds embedded article chunks.
  2. pycharm_docs_search() retrieves the most relevant chunks for a query.
  3. create_agent() builds a tool-calling ReAct loop around an Ollama LLM.
  4. ModelFallbackMiddleware retries with a backup model on LLM errors.
"""

import argparse

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama

# ---------------------------------------------------------------------------
# STEP 1 — Models
# Primary LLM: mistral is more capable.
# Fallback LLM: phi3 is lighter — used automatically if mistral fails.
# ---------------------------------------------------------------------------
llm = ChatOllama(model="mistral:latest", temperature=0)
llm_secours = ChatOllama(model="phi3:latest", temperature=0)

# ---------------------------------------------------------------------------
# STEP 2 — Vector store path
# This must match the persist_directory used in main.py when building the index.
# ---------------------------------------------------------------------------
VECTOR_STORE_PATH = "./chatbot_article_dataset"

# ---------------------------------------------------------------------------
# STEP 3 — RAG tool
# The agent calls this tool to retrieve relevant document chunks from Chroma
# before composing its answer. MMR (Maximal Marginal Relevance) diversifies
# the results so we don't get k near-identical chunks.
# ---------------------------------------------------------------------------
@tool("pycharm_docs_search")
def pycharm_docs_search(q: str) -> str:
    """Search the local Chroma index of articles and return relevant passages."""
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    # Chroma() loads an existing store — use from_documents() only when creating one.
    vector_store = Chroma(persist_directory=VECTOR_STORE_PATH, embedding_function=embeddings)
    k = 4
    retriever = vector_store.as_retriever(
        search_type="mmr", search_kwargs={"k": k, "fetch_k": max(k * 3, 12)}
    )
    docs = retriever.invoke(q)
    return "\n\n".join(doc.page_content for doc in docs)

# ---------------------------------------------------------------------------
# STEP 4 — Agent
# create_agent() wraps the LLM + tools in a LangGraph ReAct loop.
# The loop repeats: Think → Pick tool → Call tool → Observe → until done.
# ModelFallbackMiddleware transparently retries with llm_secours on errors.
# ---------------------------------------------------------------------------
system_prompt = (
    "You are a helpful assistant that answers questions about JetBrains PyCharm "
    "using the provided tools. Always consult the 'pycharm_docs_search' tool to "
    "find relevant documentation before answering. "
    "If information isn't found, say you don't know."
)

agent = create_agent(
    model=llm,
    tools=[pycharm_docs_search],
    system_prompt=system_prompt,
    middleware=[ModelFallbackMiddleware(llm_secours)],
)

# ---------------------------------------------------------------------------
# STEP 5 — CLI entry point
# Kept in __main__ so the agent is importable without side-effects.
# Usage: python lang-agent.py "How do I configure a virtual environment in PyCharm?"
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ask questions about articles via a LangChain agent (Chroma + Mistral)"
    )
    parser.add_argument("question", type=str, nargs="+", help="Your question")
    args = parser.parse_args()
    question = " ".join(args.question)

    # agent.invoke() runs the full ReAct loop and returns the final message list.
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    print(result["messages"][-1].content)
