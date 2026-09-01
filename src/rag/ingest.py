"""
Load the project docs, split them into chunks, embed them, and save the
vector store to disk. Run this once up front and again whenever a source
document changes.
"""
from pathlib import Path
from typing import List

import tiktoken
from langchain_chroma import Chroma
from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFium2Loader,  # Updated to the robust loader
    TextLoader,
)
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import config

try:
    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:
    # No network access to fetch the tiktoken vocab file. Fall back to a
    # rough chars-per-token estimate so chunking still works offline.
    _ENCODING = None


def _token_length(text: str) -> int:
    """Count tokens the same way the chunker measures chunk size."""
    if _ENCODING is not None:
        return len(_ENCODING.encode(text))
    return len(text) // 4


def load_documents(data_dir: str) -> List[Document]:
    """Read every PDF, DOCX and MD file in data_dir into Document objects."""
    docs: List[Document] = []
    folder = Path(data_dir)

    for path in sorted(folder.glob("**/*")):
        try:
            if path.suffix.lower() == ".pdf":
                # Using PyPDFium2Loader handles broken pointers smoothly
                docs.extend(PyPDFium2Loader(str(path)).load())
            elif path.suffix.lower() == ".docx":
                docs.extend(Docx2txtLoader(str(path)).load())
            elif path.suffix.lower() in (".md", ".txt"):
                docs.extend(TextLoader(str(path), encoding="utf-8").load())
        except Exception as e:
            print(f"\n Skipping corrupted file: {path.name}")
            print(f"   Reason: {e}\n")
            continue

    return docs


def _section_title(doc: Document) -> str:
    """Best-effort section label for a chunk's metadata."""
    page = doc.metadata.get("page")
    if page is not None:
        return f"Page {page + 1}"
    return "Full document"


def tag_metadata(docs: List[Document]) -> List[Document]:
    """Keep only the metadata we actually use: file name and section."""
    for doc in docs:
        source_path = Path(doc.metadata.get("source", "unknown"))
        section = _section_title(doc)
        doc.metadata = {"file_name": source_path.name, "section": section}
    return docs


def split_documents(docs: List[Document]) -> List[Document]:
    """Chunk each document to ~500 tokens with ~100 token overlap."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        length_function=_token_length,
    )
    return splitter.split_documents(docs)


def get_embeddings():
    """Pick the embedding model based on config."""
    if config.EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddings(api_key=config.OPENAI_API_KEY)
    return HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)


def build_vectorstore(chunks: List[Document]) -> Chroma:
    """Embed the chunks and persist them to the Chroma store on disk."""
    store = Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        collection_name=config.COLLECTION_NAME,
        persist_directory=config.VECTORSTORE_DIR,
    )
    return store


def run_ingest(data_dir: str = config.DATA_DIR) -> int:
    """Full pipeline: load, tag, chunk, embed, persist. Returns chunk count."""
    docs = load_documents(data_dir)
    if not docs:
        print(f"No documents found in {data_dir}")
        return 0

    docs = tag_metadata(docs)
    chunks = split_documents(docs)
    build_vectorstore(chunks)

    print(f"Ingested {len(docs)} pages/files into {len(chunks)} chunks.")
    print(f"Vector store saved to {config.VECTORSTORE_DIR}")
    return len(chunks)


if __name__ == "__main__":
    run_ingest()
