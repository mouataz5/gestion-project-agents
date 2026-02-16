"""
Code RAG for Agent 3 (Code Reviewer).

AST-aware, structure-based splitting: we chunk by functions and classes (not by
character count) and index imports as metadata so the reviewer knows where code
lives and how files relate. See PROJECT_CONTEXT.md §4.1.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

if TYPE_CHECKING:
    from langchain_core.callbacks import CallbackManagerForRetrieverRun

from .ingestion_advanced import _get_embeddings, DEFAULT_QDRANT_PATH

CODE_COLLECTION_NAME = "code_base"

_code_retriever: BaseRetriever | None = None


class _StubCodeRetriever(BaseRetriever):
    """Retriever that returns no documents when no code has been indexed."""

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun | None = None,
    ) -> list[Document]:
        return []


def _list_py_files(root: Path) -> list[Path]:
    """List all .py files under root, excluding __pycache__ and .venv."""
    out: list[Path] = []
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts or ".venv" in p.parts or "venv" in p.parts:
            continue
        out.append(p)
    return out


def _extract_imports(tree: ast.AST) -> list[str]:
    """Collect import names from AST for relationship metadata (e.g. 'os', 'pathlib.Path')."""
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for alias in node.names:
                    imports.append(f"{node.module}.{alias.name}")
            else:
                for alias in node.names:
                    imports.append(alias.name)
    return imports


def _source_segment(source: str, node: ast.FunctionDef | ast.ClassDef) -> str:
    """Return the exact source slice for a function or class node (Python 3.8+ end_lineno)."""
    lines = source.splitlines()
    start = node.lineno - 1
    end = getattr(node, "end_lineno", node.lineno)
    return "\n".join(lines[start:end])


def _chunk_file_by_ast(
    file_path: Path,
    source: str,
    rel_path: str,
) -> list[Document]:
    """
    Split a Python file into one chunk per top-level function and per top-level class.
    Metadata: file, file_path, class, function, imports (for relationship-aware retrieval).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Fallback: one document for the whole file with minimal metadata
        return [
            Document(
                page_content=source,
                metadata={
                    "source": rel_path,
                    "file_path": str(file_path),
                    "class": "",
                    "function": "",
                    "imports": [],
                },
            ),
        ]
    imports = _extract_imports(tree)
    base_meta = {
        "source": rel_path,
        "file_path": str(file_path),
        "imports": imports,
    }
    docs: list[Document] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            content = _source_segment(source, node)
            meta = {**base_meta, "class": "", "function": node.name}
            docs.append(Document(page_content=content, metadata=meta))
        elif isinstance(node, ast.ClassDef):
            content = _source_segment(source, node)
            meta = {**base_meta, "class": node.name, "function": ""}
            docs.append(Document(page_content=content, metadata=meta))
    if not docs:
        # No top-level classes/functions (e.g. only imports or module-level code)
        docs.append(
            Document(
                page_content=source,
                metadata={**base_meta, "class": "", "function": ""},
            )
        )
    return docs


def ingest_code_directory(
    directory: str | Path,
    *,
    collection_name: str = CODE_COLLECTION_NAME,
    path: str | None = None,
) -> BaseRetriever:
    """
    Index Python files under directory into Qdrant using AST-aware chunking.

    Chunks are one per top-level function and per top-level class; each chunk
    has metadata: file, file_path, class, function, imports. This allows Agent 3
    to know where code lives and how files relate (imports) instead of reviewing
    isolated character-based snippets.
    """
    global _code_retriever

    path = path or DEFAULT_QDRANT_PATH
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")

    py_files = _list_py_files(directory)
    if not py_files:
        _code_retriever = _StubCodeRetriever()
        return _code_retriever

    chunks: list[Document] = []
    for fp in py_files:
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = fp.relative_to(directory)
        chunks.extend(_chunk_file_by_ast(fp, text, str(rel)))

    if not chunks:
        _code_retriever = _StubCodeRetriever()
        return _code_retriever

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
    _code_retriever = vectorstore.as_retriever(search_kwargs={"k": 6})
    return _code_retriever


def get_code_retriever(
    collection_name: str | None = None,
    path: str | None = None,
) -> BaseRetriever:
    """
    Return the code retriever for Agent 3 (relevant code context).
    Call ingest_code_directory() first to index a repo or folder.
    """
    if _code_retriever is not None:
        return _code_retriever
    _ = collection_name
    _ = path
    return _StubCodeRetriever()
