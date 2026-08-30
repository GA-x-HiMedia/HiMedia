"""
Retrieval and generation. Given a question: find the closest chunks, build a
prompt that only allows the model to use those chunks, and return an answer
with its sources.
"""
from dataclasses import dataclass
from typing import List

from langchain_chroma import Chroma
from langchain_core.documents import Document
from openai import OpenAI

from . import config
from .ingest import get_embeddings

SYSTEM_PROMPT = (
    "You are a support assistant for the HiMedia AI Agent capstone. "
    "Answer the question using ONLY the context below. "
    "If the answer is not in the context, say you don't know — do not guess. "
    "Keep the answer short and cite each fact as (file_name, section)."
)


@dataclass
class RagAnswer:
    """The generated answer plus the chunks it was built from."""
    answer: str
    sources: List[Document]


def load_vectorstore() -> Chroma:
    """Open the vector store that ingest.py already built."""
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=config.VECTORSTORE_DIR,
    )


def retrieve(question: str, k: int = config.TOP_K) -> List[Document]:
    """Top-k chunks most relevant to the question."""
    store = load_vectorstore()
    return store.similarity_search(question, k=k)


def build_prompt(question: str, chunks: List[Document]) -> str:
    """Stitch the retrieved chunks into a context block for the model."""
    context_blocks = []
    for chunk in chunks:
        tag = f"[{chunk.metadata['file_name']} - {chunk.metadata['section']}]"
        context_blocks.append(f"{tag}\n{chunk.page_content}")
    context = "\n\n".join(context_blocks)

    return f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"


def _get_client() -> OpenAI:
    """Gemini first (our placeholder provider), OpenAI as the fallback."""
    if config.GEMINI_API_KEY:
        return OpenAI(api_key=config.GEMINI_API_KEY, base_url=config.GEMINI_BASE_URL)
    return OpenAI(api_key=config.OPENAI_API_KEY)


def generate_answer(question: str, k: int = config.TOP_K) -> RagAnswer:
    """Run the full retrieve -> prompt -> generate pipeline for one question."""
    chunks = retrieve(question, k=k)
    if not chunks:
        return RagAnswer(answer="I don't know — no matching content was found.", sources=[])

    prompt = build_prompt(question, chunks)
    client = _get_client()

    response = client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
    )

    answer = response.choices[0].message.content
    return RagAnswer(answer=answer, sources=chunks)


def format_sources(chunks: List[Document]) -> str:
    """Turn the retrieved chunks into a readable source list."""
    seen = []
    for chunk in chunks:
        tag = f"{chunk.metadata['file_name']} ({chunk.metadata['section']})"
        if tag not in seen:
            seen.append(tag)
    return "\n".join(f"- {tag}" for tag in seen)
