"""
Chat Service
Handles Q&A conversations about research papers using local Ollama
RAG (FAISS + BM25, zero cost). No OpenAI, no Pinecone.

Embeddings are nomic-embed-text (768 dim). A FAISS index is built
fresh per paper in memory and rebuilt after a restart; there is no
shared cloud index and no Pinecone index to reuse.
"""
import hashlib
import json
import logging
import os
import time
from typing import List, Dict, Optional, Tuple

from ..core.config import settings

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_classic.retrievers import EnsembleRetriever

from .llm_provider import get_models

# In-memory FAISS index per paper (built fresh, rebuilt after restart).
_faiss_stores: Dict[str, FAISS] = {}
_indexed_paper_ids: set = set()

# In-memory store of raw (pre-contextual) chunks per paper for BM25 keyword retrieval.
# BM25 is exact keyword matching — it catches what semantic search misses.
# Stored as plain text strings; rebuilt from paper text on server restart.
_paper_chunks_cache: Dict[str, List[Document]] = {}

# Fallback chat sessions when Upstash Redis is not configured (dev / single-worker).
_memory_chat_sessions: Dict[str, Tuple[List[Dict[str, str]], float]] = {}


def _use_contextual_chunk_prefix() -> bool:
    """
    If true: one LLM call per chunk at index time (slow for long papers; first answer can take many minutes).
    Default false: index raw chunks only — fast; hybrid BM25 + semantic retrieval still works well.
    Set env CHAT_CONTEXTUAL_CHUNK_PREFIX=1 to enable the slower enrichment.
    """
    v = (os.getenv("CHAT_CONTEXTUAL_CHUNK_PREFIX") or "").strip().lower()
    return v in ("1", "true", "yes")


# ── Internal helpers ───────────────────────────────────────────────────────

def _get_models(chat_model=None):
    """Return (embeddings, llm) from the local Ollama provider."""
    return get_models(chat_model)


def _make_paper_id(paper_text: str) -> str:
    """
    Derive a stable short ID from paper text.
    Use first 40 chars of SHA256 as a stable paper id.
    """
    sha = hashlib.sha256()
    sha.update(paper_text.encode("utf-8", errors="ignore"))
    return sha.hexdigest()[:40]


def make_paper_id(paper_text: str) -> str:
    """Stable paper id — first 40 hex chars of SHA256 of full text."""
    return _make_paper_id(paper_text)


def _add_context_to_chunk(chunk: Document, full_paper: str, llm) -> Document:
    """
    Contextual embeddings: prepend an AI-generated description of where this
    chunk sits in the paper before embedding it.

    This dramatically improves retrieval for vague or follow-up questions
    (e.g. "how did it perform?") because the embedding now captures section
    context, not just raw text.

    One LLM call per chunk at index time — no extra cost at query time.
    """
    # Truncate paper to stay within token budget (first 3000 chars is enough
    # for the model to understand structure without hitting limits)
    paper_preview = full_paper[:3000]

    prompt = (
        "You are helping index a research paper for retrieval.\n\n"
        f"Here is an overview of the paper:\n<paper>\n{paper_preview}\n</paper>\n\n"
        f"Here is a specific chunk from that paper:\n<chunk>\n{chunk.page_content}\n</chunk>\n\n"
        "Write 2-3 sentences describing:\n"
        "1. Which section of the paper this chunk belongs to (e.g. Abstract, Introduction, "
        "Methodology, Results, Conclusion, References).\n"
        "2. What specific concept or finding this chunk covers.\n\n"
        "Be concise and factual. Output ONLY the description — no preamble, "
        "no labels, no extra formatting."
    )

    try:
        response = llm.invoke(prompt)
        context_prefix = response.content.strip()
        contextualized_text = f"{context_prefix}\n---\n{chunk.page_content}"
        return Document(page_content=contextualized_text, metadata=chunk.metadata)
    except Exception as e:
        # If LLM call fails for any chunk, fall back to the original chunk
        # so indexing is not blocked entirely
        logging.warning(f"Context generation failed for chunk, using original: {e}")
        return chunk


def _split_to_documents(
    paper_text: str,
    paper_id: str,
    llm,
    paper_title: Optional[str] = None,
    paper_source: Optional[str] = None,
) -> Tuple[List[Document], List[Document]]:
    """
    Split paper text into chunks and attach metadata.

    Optionally (CHAT_CONTEXTUAL_CHUNK_PREFIX=1) prepends an LLM summary per chunk
    for FAISS; default is plain chunks only so the first question returns quickly.

    Returns:
        raw_chunks:            Original chunks (BM25 keyword retrieval)
        contextualized_chunks: Chunks for FAISS vector indexing
    """
    meta = {"paper_id": paper_id}
    if paper_title:
        meta["paper_title"] = paper_title
    if paper_source:
        meta["paper_source"] = paper_source

    base = Document(page_content=paper_text, metadata=meta)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""],
    )
    raw_chunks = splitter.split_documents([base])
    for c in raw_chunks:
        c.metadata.update(meta)

    n = len(raw_chunks)
    if _use_contextual_chunk_prefix():
        logging.info("Contextual chunk prefixes enabled: %s LLM calls at index time...", n)
        contextualized_chunks = [
            _add_context_to_chunk(chunk, paper_text, llm)
            for chunk in raw_chunks
        ]
        logging.info("Contextual prefix generation complete.")
    else:
        logging.info(
            "Indexing %s chunks without per-chunk LLM (fast). "
            "Set CHAT_CONTEXTUAL_CHUNK_PREFIX=1 for slower, enriched embeddings.",
            n,
        )
        contextualized_chunks = [
            Document(page_content=c.page_content, metadata=dict(c.metadata))
            for c in raw_chunks
        ]
    return raw_chunks, contextualized_chunks


def _stable_chunk_ids(chunks: List[Document], paper_id: str) -> List[str]:
    """
    Deterministic chunk IDs — safe to upsert multiple times without creating duplicates.
    """
    ids: List[str] = []
    for i, d in enumerate(chunks):
        h = hashlib.sha256()
        h.update(paper_id.encode("utf-8"))
        h.update(b"\n")
        h.update(d.page_content.encode("utf-8", errors="ignore"))
        ids.append(f"{paper_id[:12]}-{i}-{h.hexdigest()[:24]}")
    return ids


def _index_paper(
    paper_text: str,
    paper_id: str,
    llm,
    paper_title: Optional[str],
    paper_source: Optional[str],
):
    """
    Build a fresh in-memory FAISS index for one paper (768-dim
    nomic-embed-text vectors). The index is per paper and per process:
    it is rebuilt after a restart, never loaded from a Pinecone index.
    Returns the FAISS store.
    """
    global _indexed_paper_ids

    if paper_id in _indexed_paper_ids and paper_id in _faiss_stores:
        logging.debug(f"Paper {paper_id[:12]} already indexed (cached).")
        return _faiss_stores[paper_id]

    logging.info(f"Indexing paper {paper_id[:12]} into local FAISS...")
    embeddings, _llm = _get_models()
    raw_chunks, contextualized_chunks = _split_to_documents(
        paper_text,
        paper_id,
        llm=llm,
        paper_title=paper_title,
        paper_source=paper_source,
    )
    vectorstore = FAISS.from_documents(contextualized_chunks, embeddings)
    _faiss_stores[paper_id] = vectorstore
    _paper_chunks_cache[paper_id] = raw_chunks
    _indexed_paper_ids.add(paper_id)
    logging.info(f"Paper {paper_id[:12]} indexed successfully ({len(contextualized_chunks)} chunks)")
    return vectorstore


def _to_langchain_messages(
    conversation_history: Optional[List[Dict[str, str]]]
) -> List[BaseMessage]:
    """Convert conversation history dicts to LangChain message objects."""
    if not conversation_history:
        return []
    msgs: List[BaseMessage] = []
    for m in conversation_history:
        role = (m.get("role") or "").lower()
        content = m.get("content") or ""
        if not content:
            continue
        if role == "user":
            msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            msgs.append(AIMessage(content=content))
        elif role == "system":
            msgs.append(SystemMessage(content=content))
        else:
            msgs.append(HumanMessage(content=content))
    return msgs


def _build_rag_chain(llm, retriever, has_history: bool):
    """
    Build the RAG pipeline.

    FIX: The history-aware retriever rephrases queries through the LLM before
    retrieval. For the first question (empty history) this adds latency and
    can subtly distort the query, reducing retrieval quality.

    Now: history-aware retriever is only activated when there is actual
    conversation history. First questions hit the retriever directly.

    Chain 1 (conditional) — history_aware_retriever:
        Rephrases follow-up questions into standalone questions using history.
        Skipped entirely when has_history=False.

    Chain 2 — document_chain:
        Answers using retrieved context chunks.
    """
    if has_history:
        # Rephrase follow-up into standalone question using history
        condensed_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "Given the conversation history and a follow-up question, "
                "rephrase the follow-up question to be a standalone question. "
                "If it is already standalone, return it as-is. "
                "Do NOT answer it — only rephrase.",
            ),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        effective_retriever = create_history_aware_retriever(llm, retriever, condensed_prompt)
        logging.debug("Using history-aware retriever (conversation history present).")
    else:
        # No history — use retriever directly, no extra LLM call needed
        effective_retriever = retriever
        logging.debug("Using direct retriever (no conversation history).")

    # Answer using retrieved chunks + optional history
    answer_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a research assistant helping users understand a paper.\n"
            "Answer the question using the context below.\n"
            "- If the context clearly contains the answer, give a direct, detailed response.\n"
            "- If the context partially covers the question, answer what you can and note any gaps.\n"
            "- Only say 'Not found in the document' if the context has absolutely no relevant "
            "information — not just because the phrasing differs.\n\n"
            "Context:\n{context}",
        ),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    document_chain = create_stuff_documents_chain(llm, answer_prompt)

    return create_retrieval_chain(effective_retriever, document_chain)


# ── Chat session persistence (Upstash Redis or in-memory fallback) ───────

def _redis_client():
    url = settings.UPSTASH_REDIS_REST_URL
    token = settings.UPSTASH_REDIS_REST_TOKEN
    if not url or not token:
        return None
    try:
        from upstash_redis import Redis
        return Redis(url=url, token=token)
    except Exception as e:
        logging.warning("Upstash Redis unavailable: %s", e)
        return None


def _session_storage_key(session_id: str) -> str:
    return f"research-flow:paper-chat:{session_id}"


def load_session(session_id: str) -> List[Dict[str, str]]:
    """Return prior messages [{role, content}, ...] for this session."""
    if not session_id or not str(session_id).strip():
        return []
    sid = str(session_id).strip()
    client = _redis_client()
    if client:
        try:
            raw = client.get(_session_storage_key(sid))
            if raw is None:
                return []
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            data = json.loads(raw)
            if not isinstance(data, list):
                return []
            out: List[Dict[str, str]] = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                role = item.get("role") or ""
                content = item.get("content") or ""
                if content:
                    out.append({"role": str(role), "content": str(content)})
            return out
        except Exception as e:
            logging.warning("load_session Redis error: %s", e)
            return []

    now = time.time()
    entry = _memory_chat_sessions.get(sid)
    if not entry:
        return []
    messages, expires_at = entry
    if now > expires_at:
        _memory_chat_sessions.pop(sid, None)
        return []
    return list(messages)


def _save_session_messages(session_id: str, messages: List[Dict[str, str]]) -> None:
    sid = str(session_id).strip()
    ttl = max(60, int(settings.REDIS_CHAT_TTL))
    client = _redis_client()
    if client:
        try:
            client.set(_session_storage_key(sid), json.dumps(messages), ex=ttl)
        except Exception as e:
            logging.warning("save_session Redis error: %s", e)
        return
    _memory_chat_sessions[sid] = (list(messages), time.time() + ttl)


def delete_session(session_id: str) -> None:
    if not session_id or not str(session_id).strip():
        return
    sid = str(session_id).strip()
    client = _redis_client()
    if client:
        try:
            client.delete(_session_storage_key(sid))
        except Exception as e:
            logging.warning("delete_session Redis error: %s", e)
    _memory_chat_sessions.pop(sid, None)


# ── Public API ─────────────────────────────────────────────────────────────

def ask_about_paper(
    question: str,
    paper_text: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
    paper_title: Optional[str] = None,
    paper_source: Optional[str] = None,
) -> Optional[str]:
    """
    Answer a question about a research paper using local Ollama RAG (FAISS + LangChain).

    Args:
        question:             User's question about the paper
        paper_text:           Full extracted text of the paper
        conversation_history: Previous messages [{role, content}, ...]
        model:                Ollama chat model (default: settings.OLLAMA_CHAT_MODEL)
        paper_title:          Paper title stored in chunk metadata
        paper_source:         Source e.g. arXiv, CORE, PMC

    Returns:
        Answer string, or None on empty result
    """
    if not question or not question.strip():
        raise ValueError("Empty question provided")

    if not paper_text or len(paper_text.strip()) < 100:
        raise ValueError("Paper text too short or empty for Q&A")

    try:
        embeddings, llm = _get_models(model)
        paper_id = _make_paper_id(paper_text)

        # Index only when needed — llm is passed for contextual embeddings
        vectorstore = _index_paper(
            paper_text=paper_text,
            paper_id=paper_id,
            llm=llm,
            paper_title=paper_title,
            paper_source=paper_source,
        )

        # ── Retriever: Ensemble of BM25 (keyword) + FAISS (semantic) ──────
        #
        # WHY: MMR + MultiQueryRetriever were the root cause of random failures.
        #   - MMR actively discards the most relevant chunk for "diversity"
        #   - MultiQueryRetriever generates noisy rephrased queries that can
        #     pull in off-topic chunks, pushing the right chunk out of top-k
        #
        # FIX: Hybrid retrieval — BM25 catches exact keyword matches that
        # semantic search misses (e.g. specific numbers, names, acronyms).
        # FAISS semantic search catches meaning-based matches.
        # EnsembleRetriever fuses both with Reciprocal Rank Fusion (RRF),
        # which is far more stable than MMR for factual Q&A.

        # BM25 — keyword retrieval over raw (non-contextualized) chunks
        bm25_docs = _paper_chunks_cache.get(paper_id)
        if not bm25_docs:
            # Server restarted — rebuild BM25 from raw paper text (no LLM calls needed)
            logging.info(f"Rebuilding BM25 cache for paper {paper_id[:12]} after restart...")
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1200, chunk_overlap=200,
                separators=["\n\n", "\n", " ", ""],
            )
            meta = {"paper_id": paper_id}
            if paper_title:
                meta["paper_title"] = paper_title
            if paper_source:
                meta["paper_source"] = paper_source
            base_doc = Document(page_content=paper_text, metadata=meta)
            bm25_docs = splitter.split_documents([base_doc])
            for c in bm25_docs:
                c.metadata.update(meta)
            _paper_chunks_cache[paper_id] = bm25_docs

        bm25_retriever = BM25Retriever.from_documents(bm25_docs)
        bm25_retriever.k = 6

        # FAISS — pure cosine similarity (NOT MMR) for consistent top-k ranking
        faiss_retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 6},
        )

        # Ensemble — fuse both retrievers with equal weight using RRF
        retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, faiss_retriever],
            weights=[0.4, 0.6],   # slightly favour semantic; tune if needed
        )

        # Determine if there is real conversation history
        chat_history_msgs = _to_langchain_messages(conversation_history)
        has_history = len(chat_history_msgs) > 0

        # Build chain — history-aware retriever only activated when needed
        rag_chain = _build_rag_chain(llm, retriever, has_history=has_history)

        result = rag_chain.invoke({
            "input": question.strip(),
            "chat_history": chat_history_msgs,
        })

        answer = result.get("answer")
        if not isinstance(answer, str):
            answer = str(answer) if answer is not None else ""
        return answer.strip() if answer else None

    except ValueError:
        raise
    except Exception as e:
        logging.error(f"Error in chat service: {str(e)}", exc_info=True)
        raise ValueError(f"Chat error: {str(e)}")


def index_paper_text(
    paper_text: str,
    paper_title: Optional[str] = None,
    paper_source: Optional[str] = None,
) -> str:
    """Index full text into the FAISS + BM25 RAG store.

    Used by the full-text bridge: after a paper PDF is extracted,
    indexing it here makes RAG ask answer from the full text.
    Returns the stable paper id (SHA256 of the text).
    """
    if not paper_text or len(paper_text.strip()) < 100:
        raise ValueError("Paper text too short or empty for indexing")
    _, llm = _get_models()
    paper_id = _make_paper_id(paper_text)
    _index_paper(
        paper_text=paper_text,
        paper_id=paper_id,
        llm=llm,
        paper_title=paper_title,
        paper_source=paper_source,
    )
    return paper_id


def is_paper_indexed(paper_text: str) -> bool:
    """True when this exact text is already in the RAG store."""
    return _make_paper_id(paper_text) in _indexed_paper_ids


def ask_about_paper_with_session(
    session_id: str,
    question: str,
    paper_text: str,
    model: Optional[str] = None,
    paper_title: Optional[str] = None,
    paper_source: Optional[str] = None,
) -> Optional[str]:
    """
    Same as ask_about_paper but loads/stores conversation_history under session_id
    (Upstash Redis when configured, otherwise in-memory per process).
    """
    if not session_id or not str(session_id).strip():
        raise ValueError("session_id is required")
    sid = str(session_id).strip()
    history = load_session(sid)
    answer = ask_about_paper(
        question=question,
        paper_text=paper_text,
        conversation_history=history if history else None,
        model=model,
        paper_title=paper_title,
        paper_source=paper_source,
    )
    if not answer:
        return None
    new_history = history + [
        {"role": "user", "content": question.strip()},
        {"role": "assistant", "content": answer},
    ]
    _save_session_messages(sid, new_history)
    return answer
