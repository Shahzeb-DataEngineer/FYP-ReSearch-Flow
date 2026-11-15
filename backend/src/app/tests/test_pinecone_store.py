"""Unit tests for the Pinecone vector store (services/pinecone_store.py).

Every test runs against a fake ``pinecone`` module installed in
sys.modules: no real API key, no network, no live index. The fake
records the calls the store makes, so the tests verify the store's
behaviour (index creation, deterministic ids, paper_id filtering,
clear error when the key is unset) rather than Pinecone itself.

Runner: from the backend/ directory run:

    python -m unittest discover -s src/app/tests -v
"""

import sys
import types
import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from src.app.services import chat_service, pinecone_store
from src.app.services.pinecone_store import (
    PineconeNotConfiguredError,
    PineconeRetriever,
    delete_paper,
    ensure_index,
    query_paper,
    upsert_documents,
)


class _FakeEmbeddings:
    """Deterministic 768-dim embeddings: one fixed vector per text."""

    def embed_documents(self, texts):
        return [[0.1] * 768 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 768


class _FakeMatch:
    def __init__(self, chunk_id, text, score):
        self.id = chunk_id
        self.score = score
        self.metadata = {"paper_id": "paper123", "text": text}


class _FakeQueryResponse:
    def __init__(self, matches):
        self.matches = matches


class _FakeIndex:
    def __init__(self):
        self.upsert_calls = []
        self.query_calls = []
        self.delete_calls = []
        self.vectors = {}

    def upsert(self, vectors):
        self.upsert_calls.append(list(vectors))
        for v in vectors:
            self.vectors[v["id"]] = v
        return {"upserted_count": len(vectors)}

    def query(self, vector, top_k, filter, include_metadata):
        self.query_calls.append(
            {"vector": vector, "top_k": top_k, "filter": filter,
             "include_metadata": include_metadata}
        )
        return _FakeQueryResponse([
            _FakeMatch(cid, v["metadata"]["text"], 0.9)
            for cid, v in list(self.vectors.items())[:top_k]
        ])

    def delete(self, filter):
        self.delete_calls.append(filter)
        return {}


class _FakeServerlessSpec:
    def __init__(self, cloud, region):
        self.cloud = cloud
        self.region = region


class _FakePinecone:
    instances = []

    def __init__(self, api_key):
        self.api_key = api_key
        self.existing = []
        self.created = []
        self.indexes = {}
        _FakePinecone.instances.append(self)

    def list_indexes(self):
        return [{"name": name} for name in self.existing]

    def create_index(self, name, dimension, metric, spec):
        self.created.append(
            {"name": name, "dimension": dimension, "metric": metric, "spec": spec}
        )
        self.existing.append(name)

    def Index(self, name):
        if name not in self.indexes:
            self.indexes[name] = _FakeIndex()
        return self.indexes[name]


def _install_fake_pinecone():
    """Install the fake pinecone module; returns a restore function."""
    module = types.ModuleType("pinecone")
    module.Pinecone = _FakePinecone
    module.ServerlessSpec = _FakeServerlessSpec
    original = sys.modules.get("pinecone")
    sys.modules["pinecone"] = module
    _FakePinecone.instances.clear()

    def restore():
        if original is None:
            sys.modules.pop("pinecone", None)
        else:
            sys.modules["pinecone"] = original

    return restore


def _docs():
    return [
        Document(page_content="First chunk about sleep.",
                 metadata={"paper_title": "Sleep", "paper_source": "arXiv"}),
        Document(page_content="Second chunk about memory.",
                 metadata={"paper_title": "Sleep", "paper_source": "arXiv"}),
    ]


class PineconeStoreTest(unittest.TestCase):
    def setUp(self):
        self._restore_pinecone = _install_fake_pinecone()
        self.addCleanup(self._restore_pinecone)
        self._key_patch = patch.object(
            pinecone_store.settings, "PINECONE_API_KEY", "test-key"
        )
        self._key_patch.start()
        self.addCleanup(self._key_patch.stop)
        self.embeddings = _FakeEmbeddings()

    def _client(self):
        return _FakePinecone.instances[-1]

    def test_not_configured_raises_clear_error(self):
        with patch.object(pinecone_store.settings, "PINECONE_API_KEY", None):
            with self.assertRaises(PineconeNotConfiguredError) as ctx:
                upsert_documents(_docs(), self.embeddings, "paper123")
        self.assertIn("PINECONE_API_KEY", str(ctx.exception))
        self.assertIn("pinecone.io", str(ctx.exception))

    def test_ensure_index_creates_serverless_when_missing(self):
        index = ensure_index()
        client = self._client()
        self.assertEqual(len(client.created), 1)
        created = client.created[0]
        self.assertEqual(created["name"], "research-flow")
        self.assertEqual(created["dimension"], 768)
        self.assertEqual(created["metric"], "cosine")
        self.assertEqual(created["spec"].cloud, "aws")
        self.assertEqual(created["spec"].region, "us-east-1")
        self.assertIs(index, client.indexes["research-flow"])

    def test_ensure_index_skips_when_exists(self):
        client = _FakePinecone("test-key")
        client.existing = ["research-flow"]
        with patch.object(pinecone_store, "_get_client", return_value=client):
            ensure_index()
        self.assertEqual(client.created, [])

    def test_upsert_deterministic_ids_and_metadata(self):
        docs = _docs()
        index = ensure_index()
        first = upsert_documents(docs, self.embeddings, "paper123", index=index)
        self.assertEqual(first, 2)
        self.assertEqual(len(index.upsert_calls), 1)
        first_ids = [v["id"] for v in index.upsert_calls[0]]
        self.assertEqual(len(set(first_ids)), 2)
        for vector in index.upsert_calls[0]:
            self.assertEqual(vector["metadata"]["paper_id"], "paper123")
            self.assertIn("text", vector["metadata"])
            self.assertEqual(len(vector["values"]), 768)
        # Second upsert of the same paper overwrites the same ids.
        upsert_documents(docs, self.embeddings, "paper123", index=index)
        second_ids = [v["id"] for v in index.upsert_calls[1]]
        self.assertEqual(first_ids, second_ids)
        self.assertEqual(len(index.vectors), 2)

    def test_upsert_empty_documents_returns_zero(self):
        self.assertEqual(upsert_documents([], self.embeddings, "paper123"), 0)

    def test_query_filters_by_paper_id(self):
        docs = _docs()
        index = ensure_index()
        upsert_documents(docs, self.embeddings, "paper123", index=index)
        results = query_paper("paper123", "sleep", self.embeddings, top_k=6, index=index)
        self.assertEqual(len(index.query_calls), 1)
        call = index.query_calls[0]
        self.assertEqual(call["filter"], {"paper_id": {"$eq": "paper123"}})
        self.assertEqual(call["top_k"], 6)
        self.assertTrue(call["include_metadata"])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].page_content, "First chunk about sleep.")
        self.assertEqual(results[0].metadata["paper_id"], "paper123")
        self.assertAlmostEqual(results[0].metadata["score"], 0.9)

    def test_delete_paper_uses_metadata_filter(self):
        delete_paper("paper123")
        index = self._client().indexes["research-flow"]
        self.assertEqual(index.delete_calls, [{"paper_id": {"$eq": "paper123"}}])

    def test_retriever_returns_documents(self):
        index = ensure_index()
        upsert_documents(_docs(), self.embeddings, "paper123", index=index)
        retriever = PineconeRetriever(
            paper_id="paper123", embeddings=self.embeddings, index=index
        )
        results = retriever._get_relevant_documents("sleep")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(isinstance(d, Document) for d in results))

    def test_chat_index_paper_raises_without_key(self):
        with patch.object(pinecone_store.settings, "PINECONE_API_KEY", None):
            with patch.object(
                chat_service, "_get_models",
                return_value=(self.embeddings, object()),
            ):
                with self.assertRaises(PineconeNotConfiguredError) as ctx:
                    chat_service._index_paper(
                        paper_text="x" * 500,
                        paper_id="paper123",
                        llm=object(),
                        paper_title=None,
                        paper_source=None,
                    )
        self.assertIn("PINECONE_API_KEY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
