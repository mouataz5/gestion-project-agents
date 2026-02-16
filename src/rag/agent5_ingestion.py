"""
RAG for Agent 5 (Risk Predictor).

Separate from Agent 1's ingestion_advanced: own collection (risk_docs) for risk/context docs.
- ingest_pdf_for_agent5(pdf_path): load PDF, index in Qdrant collection risk_docs.
- get_agent5_retriever(): return the retriever (or stub if no ingestion yet).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

if TYPE_CHECKING:
    from langchain_core.callbacks import CallbackManagerForRetrieverRun

from .ingestion_advanced import _get_embeddings, DEFAULT_QDRANT_PATH

AGENT5_COLLECTION_NAME = "risk_docs"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100

_agent5_retriever: BaseRetriever | None = None


class _StubAgent5Retriever(BaseRetriever):
    """Retriever that returns no documents when no doc has been ingested for Agent 5."""

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
    ) -> list[Document]:
        return []


def ingest_pdf_for_agent5(
    pdf_path: str | Path,
    *,
    collection_name: str = AGENT5_COLLECTION_NAME,
    path: str | None = None,
) -> BaseRetriever:
    """
    Load a PDF, chunk it, index in Qdrant collection risk_docs (Agent 5's own collection).
    Call this before get_agent5_retriever() to have RAG context for the Risk Predictor.
    """
    global _agent5_retriever

    path = path or DEFAULT_QDRANT_PATH
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    loader = PyPDFLoader(str(pdf_path))
    documents = loader.load()
    if not documents:
        _agent5_retriever = _StubAgent5Retriever()
        return _agent5_retriever

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )
    chunks = splitter.split_documents(documents)

    os.makedirs(path, exist_ok=True)
    client = QdrantClient(path=path)
    embeddings = _get_embeddings()
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
    vectorstore.add_documents(chunks)
    _agent5_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    return _agent5_retriever


def get_agent5_retriever(
    collection_name: str | None = None,
    path: str | None = None,
) -> BaseRetriever:
    """
    Return the retriever for Agent 5 (Risk Predictor) RAG context.
    Call ingest_pdf_for_agent5() first to index risk/project docs.
    """
    if _agent5_retriever is not None:
        return _agent5_retriever
    _ = collection_name
    _ = path
    return _StubAgent5Retriever()
