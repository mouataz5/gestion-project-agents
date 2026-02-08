"""
Parent-Document RAG for Agent 1.

- ingest_pdf_advanced(pdf_path): load PDF, split into parent/child chunks,
  index in Qdrant + InMemoryStore, and set the global retriever.
- get_advanced_retriever(): return the retriever (or a stub if no ingestion yet).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from langchain_classic.retrievers import ParentDocumentRetriever
from langchain_classic.storage import InMemoryStore
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

if TYPE_CHECKING:
    from langchain_core.callbacks import CallbackManagerForRetrieverRun


# Chunk sizes per PROJECT_CONTEXT: child for search, parent for LLM context
CHILD_CHUNK_SIZE = 400
PARENT_CHUNK_SIZE = 2000
DEFAULT_COLLECTION_NAME = "project_specs"
DEFAULT_QDRANT_PATH = "./qdrant_data"

# Embedding model (local CPU)
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Module-level retriever after ingestion (in-memory docstore is not persisted)
_retriever: BaseRetriever | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    """Build HuggingFace embeddings for local CPU (all-MiniLM-L6-v2)."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
    )


class _StubRetriever(BaseRetriever):
    """Retriever that returns no documents when no PDF has been ingested."""

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
    ) -> list[Document]:
        return []


def ingest_pdf_advanced(
    pdf_path: str | Path,
    *,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    path: str | None = None,
) -> BaseRetriever:
    """
    Load a PDF, split into parent (2000 char) and child (400 char) chunks,
    index child chunks in Qdrant and parent docs in InMemoryStore,
    then set and return the ParentDocumentRetriever.

    Call this before get_advanced_retriever() to have real RAG context.
    """
    global _retriever

    path = path or DEFAULT_QDRANT_PATH
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    loader = PyPDFLoader(str(pdf_path))
    documents = loader.load()
    if not documents:
        _retriever = _StubRetriever()
        return _retriever

    os.makedirs(path, exist_ok=True)
    client = QdrantClient(path=path)
    embeddings = _get_embeddings()

    # all-MiniLM-L6-v2 has dimension 384
    vector_size = 384
    try:
        client.get_collection(collection_name)
    except Exception:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=vector_size,
                distance=qdrant_models.Distance.COSINE,
            ),
        )

    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )
    docstore = InMemoryStore()
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_CHUNK_SIZE,
        chunk_overlap=50,
        length_function=len,
    )
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_CHUNK_SIZE,
        chunk_overlap=200,
        length_function=len,
    )

    retriever = ParentDocumentRetriever(
        vectorstore=vectorstore,
        docstore=docstore,
        child_splitter=child_splitter,
        parent_splitter=parent_splitter,
    )
    retriever.add_documents(documents)
    _retriever = retriever
    return retriever


def get_advanced_retriever(
    collection_name: str | None = None,
    path: str | None = None,
) -> BaseRetriever:
    """
    Return the retriever for project-spec context (parent chunks).

    If ingest_pdf_advanced() has been called, returns the ParentDocumentRetriever.
    Otherwise returns a stub retriever (empty results) so the graph still runs.
    """
    if _retriever is not None:
        return _retriever
    _ = collection_name
    _ = path
    return _StubRetriever()
