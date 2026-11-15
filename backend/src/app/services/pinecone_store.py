"""
Pinecone vector store for RAG chat.

Embeddings stay local (nomic-embed-text, 768 dim, via Ollama); only
the vectors live in Pinecone. The RAG store is one serverless index
(default name ``research-flow``), with one paper's chunks isolated
by a ``paper_id`` metadata filter, so many papers share the index
without seeing each other's chunks.

Free tier: Pinecone Starter is $0 with no credit card (2 GB storage,
2M write units and 1M read units per month, 5 indexes). Starter runs
on AWS us-east-1 only, so the defaults here are the Starter limits.
Paid Standard starts at a $50/month minimum: nothing in this module
auto-upgrades, and the index is always created serverless.

Chunk ids are deterministic (paper id + chunk number + content hash),
so upserting the same paper twice overwrites the same vectors instead
of duplicating them, and a restart just re-upserts.

When PINECONE_API_KEY is unset, every operation raises
PineconeNotConfiguredError with a clear message. The RAG path does
not silently fall back to a local store: the old in-memory FAISS
index is gone from this path, and a silent fallback would hide a
missing key behind wrong-looking answers.
"""
import hashlib
import logging
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from ..core.config import settings

logger = logging.getLogger(__name__)

EMBED_DIMENSION = 768
DEFAULT_INDEX_NAME = "research-flow"
DEFAULT_CLOUD = "aws"
DEFAULT_REGION = "us-east-1"
_UPSERT_BATCH_SIZE = 100


class PineconeNotConfiguredError(ValueError):
    """Pinecone key missing: RAG chat cannot run without the store."""


def is_pinecone_configured() -> bool:
    """True when a Pinecone API key is set in the environment."""
    return bool((settings.PINECONE_API_KEY or "").strip())


def _require_configured() -> str:
    api_key = (settings.PINECONE_API_KEY or "").strip()
    if not api_key:
        raise PineconeNotConfiguredError(
            "Pinecone is not configured: set PINECONE_API_KEY in "
            "backend/.env (free Starter key from pinecone.io, no "
            "credit card). RAG chat needs the Pinecone index; see "
            "docs/DEPLOYMENT.md for the setup steps."
        )
    return api_key


def _get_client():
    """Build a Pinecone client. Import is lazy so the backend still boots when the SDK is absent."""
    api_key = _require_configured()
    try:
        from pinecone import Pinecone
    except ImportError as e:
        raise PineconeNotConfiguredError(
            "Pinecone SDK is not installed: run "
            "pip install pinecone (see backend/requirements.txt)."
        ) from e
    return Pinecone(api_key=api_key)


def _index_names(client) -> List[str]:
    """Names of existing indexes, tolerating the dict and object shapes list_indexes returns."""
    names: List[str] = []
    for item in client.list_indexes():
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = getattr(item, "name", None)
        if name:
            names.append(str(name))
    return names


def ensure_index(client=None):
    """Create the serverless index if it does not exist yet, then return it.

    The index is 768 dimensions with cosine similarity, to match
    nomic-embed-text. Creating is guarded: a missing index never
    crashes boot when no key is set, because _get_client raises
    first and callers handle it.
    """
    index_name = (settings.PINECONE_INDEX_NAME or DEFAULT_INDEX_NAME).strip()
    cloud = (settings.PINECONE_CLOUD or DEFAULT_CLOUD).strip()
    region = (settings.PINECONE_REGION or DEFAULT_REGION).strip()
    pc = client or _get_client()
    if index_name not in _index_names(pc):
        from pinecone import ServerlessSpec

        logger.info(
            "Creating Pinecone serverless index %s (%s/%s, dim %d, cosine)...",
            index_name, cloud, region, EMBED_DIMENSION,
        )
        pc.create_index(
            name=index_name,
            dimension=EMBED_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud=cloud, region=region),
        )
    return pc.Index(index_name)


def _chunk_id(paper_id: str, chunk_index: int, text: str) -> str:
    """Deterministic chunk id: safe to upsert repeatedly without duplicates."""
    h = hashlib.sha256()
    h.update(paper_id.encode("utf-8"))
    h.update(b"\n")
    h.update(text.encode("utf-8", errors="ignore"))
    return f"{paper_id[:12]}-{chunk_index}-{h.hexdigest()[:24]}"


def upsert_documents(
    documents: List[Document],
    embeddings,
    paper_id: str,
    index=None,
) -> int:
    """Embed chunks locally and upsert them into Pinecone.

    Metadata per vector: paper_id, paper_title, paper_source, and
    the chunk text itself (chunks are ~1200 chars, well under the
    40 KB per-vector metadata limit). Returns the number of vectors
    upserted. Idempotent: same paper upserted twice overwrites.
    """
    if not documents:
        return 0
    pinecone_index = index or ensure_index()
    texts = [d.page_content for d in documents]
    vectors = embeddings.embed_documents(texts)
    records = []
    for i, (doc, values) in enumerate(zip(documents, vectors)):
        meta = {"paper_id": paper_id, "text": doc.page_content}
        for key in ("paper_title", "paper_source"):
            if doc.metadata.get(key):
                meta[key] = doc.metadata[key]
        records.append(
            {"id": _chunk_id(paper_id, i, doc.page_content), "values": values, "metadata": meta}
        )
    for start in range(0, len(records), _UPSERT_BATCH_SIZE):
        pinecone_index.upsert(vectors=records[start:start + _UPSERT_BATCH_SIZE])
    logger.info("Upserted %d chunks for paper %s into Pinecone.", len(records), paper_id[:12])
    return len(records)


def _match_to_document(match) -> Optional[Document]:
    """One Pinecone match to a LangChain Document, tolerating dict or object matches."""
    if isinstance(match, dict):
        meta = match.get("metadata") or {}
        score = match.get("score")
    else:
        meta = getattr(match, "metadata", None) or {}
        score = getattr(match, "score", None)
    text = meta.get("text")
    if not text:
        return None
    metadata = {"paper_id": meta.get("paper_id")}
    for key in ("paper_title", "paper_source"):
        if meta.get(key):
            metadata[key] = meta[key]
    if score is not None:
        metadata["score"] = score
    return Document(page_content=text, metadata=metadata)


def query_paper(
    paper_id: str,
    query_text: str,
    embeddings,
    top_k: int = 6,
    index=None,
) -> List[Document]:
    """Semantic search over one paper's chunks in Pinecone.

    The query is filtered to this paper_id, so other papers in the
    shared index never leak into the results. Returns Documents in
    score order.
    """
    pinecone_index = index or ensure_index()
    query_vector = embeddings.embed_query(query_text)
    response = pinecone_index.query(
        vector=query_vector,
        top_k=top_k,
        filter={"paper_id": {"$eq": paper_id}},
        include_metadata=True,
    )
    if isinstance(response, dict):
        matches = response.get("matches") or []
    else:
        matches = getattr(response, "matches", None) or []
    docs = []
    for match in matches:
        doc = _match_to_document(match)
        if doc is not None:
            docs.append(doc)
    return docs


def delete_paper(paper_id: str, index=None) -> None:
    """Delete every vector of one paper from the index."""
    pinecone_index = index or ensure_index()
    pinecone_index.delete(filter={"paper_id": {"$eq": paper_id}})
    logger.info("Deleted Pinecone vectors for paper %s.", paper_id[:12])


class PineconeRetriever(BaseRetriever):
    """LangChain retriever over one paper's chunks in Pinecone.

    Passed to the EnsembleRetriever in chat_service.py alongside the
    BM25 retriever, exactly where the old FAISS retriever sat.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    paper_id: str
    top_k: int = 6
    embeddings: Any = None
    index: Any = None

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:
        return query_paper(
            self.paper_id,
            query,
            self.embeddings,
            top_k=self.top_k,
            index=self.index,
        )
