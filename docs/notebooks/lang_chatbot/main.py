
"""
Welcome student! Today we're building a RAG (Retrieval-Augmented Generation) pipeline.
This script demonstrates how to take external data (web articles), store it in a vector database,
and then use an LLM to answer questions about that specific data with conversation memory.
"""

import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import WebBaseLoader
from langchain_ollama import OllamaLLM
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage

# These are the URLs we want our AI to "read" and learn from.
articles = [
    'https://www.digitaltrends.com/computing/claude-sonnet-vs-gpt-4o-comparison/',
    'https://www.digitaltrends.com/computing/apple-intelligence-proves-that-macbooks-need-something-more/',
    'https://www.digitaltrends.com/computing/how-to-use-openai-chatgpt-text-generation-chatbot/',
    'https://www.digitaltrends.com/computing/character-ai-how-to-use/',
    'https://www.digitaltrends.com/computing/how-to-upload-pdf-to-chatgpt/'
]

# --- STEP 1: Document Loading ---
# Think of this as the "Ingestion" phase. WebBaseLoader scrapes the HTML content
# from the URLs and turns them into LangChain Document objects.
print("Loading articles...")
os.environ.setdefault("USER_AGENT", "BibOps-RAG-Demo/1.0")
loader = WebBaseLoader(web_paths=articles)
docs_not_split = loader.load()

# --- STEP 2: Text Splitting (Chunking) ---
# LLMs have a limit on how much text they can process at once (context window).
# We split large documents into smaller "chunks" so we can find the most relevant
# pieces later. 1000 characters per chunk is a common starting point.
print("Splitting documents into chunks...")
text_splitter = CharacterTextSplitter(chunk_size=10000, chunk_overlap=0)
docs = text_splitter.split_documents(docs_not_split)

# --- STEP 3: Vector Embeddings ---
# Computers don't understand words; they understand numbers.
# Embeddings convert text into long lists of numbers (vectors) that capture meaning.
# "all-MiniLM-L6-v2" is a great, lightweight model for this.
print("Initializing embedding model...")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# --- STEP 4: Vector Store (The Brain) ---
# We store our chunks and their embeddings in Chroma (local, no token needed).
# This allows us to do "similarity search" to find chunks that match a user's question.
dataset_path = "chatbot_article_dataset"
print("Adding documents to Chroma...")
db = Chroma.from_documents(docs, embedding=embeddings, persist_directory=dataset_path)

# --- STEP 5: Retrieval ---
# Now we ask a question. The system searches the vector store for the
# chunks most similar to our query.
query = "how to check disk usage in linux?"
print(f"Searching for context for query: '{query}'")
results = db.similarity_search(query)

# We extract the text from the retrieved documents and join them into one string.
retrieved_chunks = [doc.page_content for doc in results]
chunks_formatted = "\n\n".join(retrieved_chunks)

# --- STEP 6: Memory ---
# To make it "conversational," we keep a simple list of messages (chat history).
chat_history: list = []

# --- STEP 7: Prompting (LCEL chain) ---
# The PromptTemplate is the "personality" and "instructions" for the LLM.
# We use LCEL (|) to pipe: prompt → llm → output parser.
template = """You are an exceptional customer support chatbot that gently answers questions.
{chat_history}
You know the following context information.
{chunks_formatted}
Answer the following question from a customer. Use only information from the previous context information. Do not invent stuff.
Question: {input}
Answer:"""

prompt = PromptTemplate(
    input_variables=["chat_history", "chunks_formatted", "input"],
    template=template,
)

# --- STEP 8: LLM & Chain Execution ---
# We use OllamaLLM to run a local LLM (phi3).
# Temperature 0 makes the model's output more focused and less "creative" (safer for support).
llm = OllamaLLM(model="mistral:latest", temperature=0)

# LCEL chain: prompt | llm | parser
chain = prompt | llm | StrOutputParser()


def format_history(messages: list) -> str:
    lines = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            lines.append(f"Human: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"Assistant: {msg.content}")
    return "\n".join(lines)


# Finally, run the chain with our query and the context we retrieved earlier.
print("Generating response...")
response = chain.invoke({
    "input": query,
    "chunks_formatted": chunks_formatted,
    "chat_history": format_history(chat_history),
})

# Update memory
chat_history.append(HumanMessage(content=query))
chat_history.append(AIMessage(content=response))

print("\n--- RESPONSE ---")
print(response)
