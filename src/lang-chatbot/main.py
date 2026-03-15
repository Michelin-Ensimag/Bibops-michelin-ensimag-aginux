
"""
Welcome student! Today we're building a RAG (Retrieval-Augmented Generation) pipeline.
This script demonstrates how to take external data (web articles), store it in a vector database,
and then use an LLM to answer questions about that specific data with conversation memory.
"""

import os
from langchain.chains.llm import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.llms.ollama import Ollama
from langchain_text_splitters import CharacterTextSplitter
from langchain_deeplake import DeeplakeVectorStore
from langchain.prompts import PromptTemplate

# --- STEP 1: Configuration and API Keys ---
# We need an ActiveLoop token to interact with DeepLake if we were using their cloud,
# but here we're mostly setting it up for local/cloud compatibility.
ACTIVELOOP_TOKEN = ""
os.environ["ACTIVELOOP_TOKEN"] = ACTIVELOOP_TOKEN

# These are the URLs we want our AI to "read" and learn from.
articles = [
    'https://www.digitaltrends.com/computing/claude-sonnet-vs-gpt-4o-comparison/',
    'https://www.digitaltrends.com/computing/apple-intelligence-proves-that-macbooks-need-something-more/',
    'https://www.digitaltrends.com/computing/how-to-use-openai-chatgpt-text-generation-chatbot/',
    'https://www.digitaltrends.com/computing/character-ai-how-to-use/',
    'https://www.digitaltrends.com/computing/how-to-upload-pdf-to-chatgpt/'
]

# --- STEP 2: Document Loading ---
# Think of this as the "Ingestion" phase. WebBaseLoader scrapes the HTML content 
# from the URLs and turns them into LangChain Document objects.
print("Loading articles...")
loader = WebBaseLoader(web_paths=articles)
docs_not_split = loader.load()

# --- STEP 3: Text Splitting (Chunking) ---
# LLMs have a limit on how much text they can process at once (context window).
# We split large documents into smaller "chunks" so we can find the most relevant 
# pieces later. 1000 characters per chunk is a common starting point.
print("Splitting documents into chunks...")
text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
docs = text_splitter.split_documents(docs_not_split)

# --- STEP 4: Vector Embeddings ---
# Computers don't understand words; they understand numbers. 
# Embeddings convert text into long lists of numbers (vectors) that capture meaning.
# "all-MiniLM-L6-v2" is a great, lightweight model for this.
print("Initializing embedding model...")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# --- STEP 5: Vector Store (The Brain) ---
# We store our chunks and their embeddings in DeepLake. 
# This allows us to do "similarity search" to find chunks that match a user's question.
dataset_path = "./jetbrains_article_dataset"
db = DeeplakeVectorStore(
    dataset_path=dataset_path,
    embedding_function=embeddings,
)

# Adding our processed documents to the vector database.
print("Adding documents to DeepLake...")
db.add_documents(docs)

# --- STEP 6: Retrieval ---
# Now we ask a question. The system searches the vector store for the 
# chunks most similar to our query.
query = "how to check disk usage in linux?"
print(f"Searching for context for query: '{query}'")
results = db.similarity_search(query)

# We extract the text from the retrieved documents and join them into one string.
retrieved_chunks = [doc.page_content for doc in results]
chunks_formatted = "\n\n".join(retrieved_chunks)

# --- STEP 7: Memory & Prompting ---
# To make it "conversational," we use memory to track the history of the chat.
memory = ConversationBufferMemory(memory_key="chat_history", input_key="input")

# The PromptTemplate is the "personality" and "instructions" for the LLM.
# We tell it exactly how to use the retrieved context and the chat history.
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
# We use Ollama to run a local LLM (phi3). 
# Temperature 0 makes the model's output more focused and less "creative" (safer for support).
llm = Ollama(model="phi3:latest", temperature=0)

# The LLMChain ties everything together: the Model, the Prompt, and the Memory.
chain = LLMChain(
    llm=llm,
    prompt=prompt,
    memory=memory
)

# Finally, we run the chain with our query and the context we retrieved earlier.
print("Generating response...")
input_data = {
    "input": query,
    "chunks_formatted": chunks_formatted,
    "chat_history": memory.buffer
}

response = chain.predict(**input_data)
print("\n--- RESPONSE ---")
print(response)


