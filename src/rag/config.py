"""
Reads environment variables for the RAG pipeline. No logic, no requests here
— same rule the rest of this repo follows for config.py.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Where source documents live and where the vector store gets persisted.
DATA_DIR = os.getenv("RAG_DATA_DIR", "data/docs")
VECTORSTORE_DIR = os.getenv("RAG_VECTORSTORE_DIR", "vectorstore")
COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "himedia_docs")

# Chunking. Sizes are in tokens, not characters.
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))

# Retrieval.
TOP_K = int(os.getenv("RAG_TOP_K", "4"))

# Embeddings — local HuggingFace model by default so ingestion works with
# no API key. Set RAG_EMBEDDING_PROVIDER=openai to embed with OpenAI instead.
EMBEDDING_PROVIDER = os.getenv("RAG_EMBEDDING_PROVIDER", "huggingface")
EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Generation — reuses the same OpenAI-compatible keys as agent/config.py.
# Gemini is tried first (our placeholder provider), OpenAI is the fallback.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
CHAT_MODEL = os.getenv(
    "RAG_CHAT_MODEL",
    "gemini-3.6-flash" if GEMINI_API_KEY else "gpt-4o-mini",
)
