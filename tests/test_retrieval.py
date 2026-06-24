"""Tests for the Phase 5 RAG layer.

Covers all 8 modules: document_loader, text_extractor, chunker, embeddings,
vector_store, retriever, metadata_filter, context_formatter.

Runs without OpenAI billing credits — all embedding calls use the deterministic
mock fallback. ChromaDB tests use an isolated EphemeralClient (no disk I/O).
"""

import math

import chromadb
import pytest
from langchain_core.documents import Document
from pathlib import Path

from config.constants import TicketCategory
from rag.chunker import chunk_documents, chunk_texts
from rag.context_formatter import format_context, format_similar_cases
from rag.document_loader import load_documents_for_category, load_policy_documents
from rag.embeddings import (
    EMBEDDING_DIMENSIONS,
    _mock_embedding,
    get_embedding,
    get_embeddings,
)
from rag.metadata_filter import filter_by_category, filter_by_source, get_relevant_sources
from rag.retriever import retrieve_policy_chunks, retrieve_similar_tickets
from rag.text_extractor import extract_text, extract_texts
from rag.vector_store import (
    POLICY_COLLECTION,
    TICKETS_COLLECTION,
    add_documents,
    delete_collection,
    query_collection,
)

PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def change_to_project_root(monkeypatch):
    """Ensure all tests run from the project root so relative paths resolve."""
    monkeypatch.chdir(PROJECT_ROOT)


@pytest.fixture
def ephemeral_chroma(monkeypatch):
    """Replace _get_client with an in-memory ChromaDB client (no disk I/O)."""
    client = chromadb.EphemeralClient()
    monkeypatch.setattr("rag.vector_store._get_client", lambda: client)
    return client


@pytest.fixture
def sample_docs():
    return [
        Document(
            page_content="Refunds are processed within 5-7 business days.",
            metadata={
                "source": "refund_policy.md",
                "chunk_index": 0,
                "categories": ["Refund"],
            },
        ),
        Document(
            page_content="Billing cycles renew on the same day each month.",
            metadata={
                "source": "billing_policy.md",
                "chunk_index": 1,
                "categories": ["Billing"],
            },
        ),
    ]


@pytest.fixture
def seeded_policy(ephemeral_chroma, sample_docs):
    """Seed POLICY_COLLECTION with sample documents for retrieval tests."""
    add_documents(sample_docs, collection_name=POLICY_COLLECTION)
    return sample_docs


# ---------------------------------------------------------------------------
# document_loader
# ---------------------------------------------------------------------------


class TestDocumentLoader:
    def test_load_all_returns_four_documents(self):
        docs = load_policy_documents()
        assert len(docs) == 4

    def test_each_doc_has_source_metadata(self):
        docs = load_policy_documents()
        for doc in docs:
            assert "source" in doc.metadata
            assert doc.metadata["source"].endswith(".md")

    def test_each_doc_has_doc_type_policy(self):
        docs = load_policy_documents()
        for doc in docs:
            assert doc.metadata.get("doc_type") == "policy"

    def test_each_doc_has_non_empty_content(self):
        docs = load_policy_documents()
        for doc in docs:
            assert len(doc.page_content) > 0

    def test_load_for_refund_category_includes_refund_policy(self):
        docs = load_documents_for_category(TicketCategory.REFUND)
        sources = [d.metadata["source"] for d in docs]
        assert "refund_policy.md" in sources

    def test_load_for_billing_category_includes_billing_policy(self):
        docs = load_documents_for_category(TicketCategory.BILLING)
        sources = [d.metadata["source"] for d in docs]
        assert "billing_policy.md" in sources

    def test_load_for_technical_support_category(self):
        docs = load_documents_for_category(TicketCategory.TECHNICAL_SUPPORT)
        sources = [d.metadata["source"] for d in docs]
        assert "technical_support_guide.md" in sources

    def test_load_for_unknown_category_returns_empty(self):
        docs = load_documents_for_category("NonExistentCategory")
        assert docs == []


# ---------------------------------------------------------------------------
# text_extractor
# ---------------------------------------------------------------------------


class TestTextExtractor:
    def test_strips_h2_heading(self):
        doc = Document(page_content="## Section Title\nContent here.", metadata={})
        result = extract_text(doc)
        assert "##" not in result
        assert "Content here." in result

    def test_strips_h1_heading(self):
        doc = Document(page_content="# Main Title\nBody text.", metadata={})
        result = extract_text(doc)
        assert "#" not in result
        assert "Body text." in result

    def test_strips_bold_asterisks(self):
        doc = Document(page_content="This is **bold** text.", metadata={})
        result = extract_text(doc)
        assert "**" not in result
        assert "bold" in result

    def test_strips_inline_code(self):
        doc = Document(page_content="Call the `reset_password` endpoint.", metadata={})
        result = extract_text(doc)
        assert "`" not in result
        assert "reset_password" in result

    def test_strips_markdown_link(self):
        doc = Document(page_content="See [our docs](https://example.com).", metadata={})
        result = extract_text(doc)
        assert "https://example.com" not in result
        assert "our docs" in result

    def test_strips_italic_underscores(self):
        doc = Document(page_content="This is _italic_ text.", metadata={})
        result = extract_text(doc)
        assert "_" not in result
        assert "italic" in result

    def test_extract_texts_returns_same_count(self):
        docs = [
            Document(page_content="## Title\nText one.", metadata={}),
            Document(page_content="**Bold** text two.", metadata={}),
        ]
        results = extract_texts(docs)
        assert len(results) == 2

    def test_extract_texts_all_cleaned(self):
        docs = [
            Document(page_content="## Title\nText one.", metadata={}),
            Document(page_content="**Bold** text two.", metadata={}),
        ]
        results = extract_texts(docs)
        assert "##" not in results[0]
        assert "**" not in results[1]


# ---------------------------------------------------------------------------
# chunker
# ---------------------------------------------------------------------------


class TestChunker:
    def test_chunk_documents_produces_more_chunks_than_docs(self):
        docs = load_policy_documents()
        chunks = chunk_documents(docs)
        assert len(chunks) > len(docs)

    def test_all_chunks_have_chunk_index(self):
        docs = load_policy_documents()[:1]
        chunks = chunk_documents(docs)
        for chunk in chunks:
            assert "chunk_index" in chunk.metadata

    def test_chunks_inherit_source_metadata(self):
        docs = load_policy_documents()[:1]
        source = docs[0].metadata["source"]
        chunks = chunk_documents(docs)
        for chunk in chunks:
            assert chunk.metadata.get("source") == source

    def test_chunk_content_is_non_empty(self):
        docs = load_policy_documents()[:1]
        chunks = chunk_documents(docs)
        for chunk in chunks:
            assert len(chunk.page_content) > 0

    def test_chunk_texts_creates_documents_from_strings(self):
        texts = ["First text block.", "Second text block."]
        chunks = chunk_texts(texts, metadatas=[{"id": 1}, {"id": 2}])
        assert len(chunks) >= 2
        assert all(hasattr(c, "page_content") for c in chunks)

    def test_chunk_texts_without_metadata(self):
        texts = ["Some text without metadata."]
        chunks = chunk_texts(texts)
        assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# embeddings
# ---------------------------------------------------------------------------


class TestEmbeddings:
    def test_mock_embedding_returns_correct_dimension(self):
        vec = _mock_embedding("test text")
        assert len(vec) == EMBEDDING_DIMENSIONS

    def test_mock_embedding_is_unit_normalised(self):
        vec = _mock_embedding("normalisation check")
        norm = math.sqrt(sum(x**2 for x in vec))
        assert abs(norm - 1.0) < 1e-6

    def test_mock_embedding_is_deterministic(self):
        text = "same input text always"
        assert _mock_embedding(text) == _mock_embedding(text)

    def test_different_texts_produce_different_vectors(self):
        assert _mock_embedding("billing dispute") != _mock_embedding("password reset")

    def test_get_embedding_returns_list_of_correct_length(self):
        vec = get_embedding("customer support query")
        assert isinstance(vec, list)
        assert len(vec) == EMBEDDING_DIMENSIONS

    def test_get_embeddings_batch_count_matches_input(self):
        texts = ["query one", "query two", "query three"]
        vecs = get_embeddings(texts)
        assert len(vecs) == 3

    def test_get_embeddings_all_correct_dimension(self):
        vecs = get_embeddings(["a", "b"])
        assert all(len(v) == EMBEDDING_DIMENSIONS for v in vecs)


# ---------------------------------------------------------------------------
# vector_store
# ---------------------------------------------------------------------------


class TestVectorStore:
    def test_add_documents_returns_correct_count(self, ephemeral_chroma, sample_docs):
        count = add_documents(sample_docs, collection_name="test_add")
        assert count == len(sample_docs)

    def test_add_empty_list_returns_zero(self, ephemeral_chroma):
        count = add_documents([], collection_name="test_empty")
        assert count == 0

    def test_query_returns_expected_structure(self, seeded_policy):
        results = query_collection(
            "refund processing time",
            collection_name=POLICY_COLLECTION,
            n_results=2,
        )
        assert all("document" in r for r in results)
        assert all("metadata" in r for r in results)
        assert all("distance" in r for r in results)
        assert all("id" in r for r in results)

    def test_query_n_results_respected(self, seeded_policy):
        results = query_collection("billing", collection_name=POLICY_COLLECTION, n_results=1)
        assert len(results) == 1

    def test_query_empty_collection_returns_empty_list(self, ephemeral_chroma):
        results = query_collection("any query", collection_name="empty_col", n_results=3)
        assert results == []

    def test_delete_nonexistent_collection_is_noop(self, ephemeral_chroma):
        # Must not raise
        delete_collection("this_collection_does_not_exist_xyz")

    def test_metadata_list_fields_stored_as_string(self, ephemeral_chroma, sample_docs):
        """categories (list) must be serialised to a string for ChromaDB compatibility."""
        add_documents(sample_docs, collection_name="test_meta")
        results = query_collection("refund", collection_name="test_meta", n_results=1)
        assert len(results) == 1
        cats = results[0]["metadata"]["categories"]
        assert isinstance(cats, str), "categories must be a comma-separated string after round-trip"

    def test_upsert_is_idempotent(self, ephemeral_chroma, sample_docs):
        """Adding the same docs twice should not raise and collection count stays the same."""
        add_documents(sample_docs, collection_name="test_idempotent")
        add_documents(sample_docs, collection_name="test_idempotent")
        results = query_collection("refund", collection_name="test_idempotent", n_results=5)
        assert len(results) == len(sample_docs)


# ---------------------------------------------------------------------------
# retriever
# ---------------------------------------------------------------------------


class TestRetriever:
    def test_retrieve_policy_chunks_returns_list(self, seeded_policy):
        results = retrieve_policy_chunks("refund policy")
        assert isinstance(results, list)

    def test_retrieve_policy_chunks_count_respects_n(self, seeded_policy):
        results = retrieve_policy_chunks("billing cycle", n_results=1)
        assert len(results) == 1

    def test_retrieve_policy_chunks_each_has_document(self, seeded_policy):
        results = retrieve_policy_chunks("policy", n_results=2)
        for r in results:
            assert "document" in r
            assert isinstance(r["document"], str)

    def test_retrieve_similar_tickets_empty_collection_returns_empty(self, ephemeral_chroma):
        results = retrieve_similar_tickets("login issue")
        assert results == []


# ---------------------------------------------------------------------------
# metadata_filter
# ---------------------------------------------------------------------------


class TestMetadataFilter:
    def test_filter_by_source_keeps_matching_result(self):
        results = [
            {"metadata": {"source": "refund_policy.md"}, "document": "text1"},
            {"metadata": {"source": "billing_policy.md"}, "document": "text2"},
        ]
        filtered = filter_by_source(results, "refund_policy.md")
        assert len(filtered) == 1
        assert filtered[0]["metadata"]["source"] == "refund_policy.md"

    def test_filter_by_source_no_match_returns_empty(self):
        results = [{"metadata": {"source": "billing_policy.md"}, "document": "text"}]
        assert filter_by_source(results, "technical_support_guide.md") == []

    def test_filter_by_source_empty_input_returns_empty(self):
        assert filter_by_source([], "refund_policy.md") == []

    def test_filter_by_category_comma_separated_string(self):
        results = [
            {"metadata": {"categories": "Refund, Billing"}, "document": "text1"},
            {"metadata": {"categories": "Technical Support"}, "document": "text2"},
        ]
        filtered = filter_by_category(results, "Refund")
        assert len(filtered) == 1

    def test_filter_by_category_no_match_returns_empty(self):
        results = [{"metadata": {"categories": "Billing"}, "document": "text"}]
        assert filter_by_category(results, "Account Access") == []

    def test_filter_by_category_empty_input_returns_empty(self):
        assert filter_by_category([], "Refund") == []

    def test_get_relevant_sources_refund(self):
        sources = get_relevant_sources(TicketCategory.REFUND)
        assert "refund_policy.md" in sources

    def test_get_relevant_sources_technical_support(self):
        sources = get_relevant_sources(TicketCategory.TECHNICAL_SUPPORT)
        assert "technical_support_guide.md" in sources

    def test_get_relevant_sources_unknown_returns_empty(self):
        assert get_relevant_sources("Unknown") == []


# ---------------------------------------------------------------------------
# context_formatter
# ---------------------------------------------------------------------------


class TestContextFormatter:
    def test_format_context_includes_source_label(self):
        results = [{"metadata": {"source": "refund_policy.md"}, "document": "Refunds take 5-7 days."}]
        output = format_context(results)
        assert "[Source: refund_policy.md]" in output
        assert "Refunds take 5-7 days." in output

    def test_format_context_respects_max_chunks(self):
        results = [
            {"metadata": {"source": f"policy_{i}.md"}, "document": f"Text {i}."}
            for i in range(10)
        ]
        output = format_context(results, max_chunks=3)
        assert output.count("[Source:") == 3

    def test_format_context_empty_returns_no_info_message(self):
        output = format_context([])
        assert "No relevant policy" in output

    def test_format_context_separator_present_for_multiple_chunks(self):
        results = [
            {"metadata": {"source": "policy_a.md"}, "document": "Text A."},
            {"metadata": {"source": "policy_b.md"}, "document": "Text B."},
        ]
        output = format_context(results)
        assert "---" in output

    def test_format_similar_cases_includes_ticket_id_and_classification(self):
        results = [
            {
                "metadata": {"ticket_id": "TKT-001", "classification": "Refund"},
                "document": "Customer requested refund.",
            }
        ]
        output = format_similar_cases(results)
        assert "[Similar Case: TKT-001 | Refund]" in output
        assert "Customer requested refund." in output

    def test_format_similar_cases_empty_returns_no_cases_message(self):
        output = format_similar_cases([])
        assert "No similar historical cases" in output

    def test_format_similar_cases_respects_max_cases(self):
        results = [
            {
                "metadata": {"ticket_id": f"TKT-{i:03d}", "classification": "Billing"},
                "document": f"Ticket {i}.",
            }
            for i in range(5)
        ]
        output = format_similar_cases(results, max_cases=2)
        assert output.count("[Similar Case:") == 2


# ---------------------------------------------------------------------------
# Real-embedding semantic tests — activate once OpenAI billing credits are loaded
#
# HOW TO ACTIVATE:
#   1. Add credits at https://platform.openai.com/settings/billing
#   2. Re-ingest policy docs to replace mock vectors:
#        from rag.vector_store import delete_collection, POLICY_COLLECTION, add_documents
#        from rag.document_loader import load_policy_documents
#        from rag.chunker import chunk_documents
#        delete_collection(POLICY_COLLECTION)
#        add_documents(chunk_documents(load_policy_documents()), POLICY_COLLECTION)
#   3. Remove the @pytest.mark.skip decorator from the class below
#   4. Run: .venv/bin/pytest tests/test_retrieval.py::TestRealEmbeddingRetrieval -v
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Requires OpenAI billing credits — remove skip after re-ingesting with real embeddings")
class TestRealEmbeddingRetrieval:
    """Semantic accuracy tests that only make sense with real OpenAI embeddings.

    With mock embeddings, retrieved chunks are random (no semantic meaning).
    With text-embedding-3-small, queries should surface genuinely relevant chunks.
    These tests use the live data/chroma_db/ collection (no ephemeral monkeypatch).
    """

    def test_refund_query_returns_refund_policy_chunk(self):
        """A refund question should rank refund_policy.md in the top results."""
        results = retrieve_policy_chunks("I want a refund for my annual subscription", n_results=3)
        sources = [r["metadata"].get("source") for r in results]
        assert "refund_policy.md" in sources, (
            f"Expected refund_policy.md in top 3, got: {sources}"
        )

    def test_billing_query_returns_billing_policy_chunk(self):
        """A billing question should surface billing_policy.md."""
        results = retrieve_policy_chunks("Why was I charged twice this month?", n_results=3)
        sources = [r["metadata"].get("source") for r in results]
        assert "billing_policy.md" in sources, (
            f"Expected billing_policy.md in top 3, got: {sources}"
        )

    def test_technical_query_returns_technical_support_chunk(self):
        """A login/technical question should surface technical_support_guide.md."""
        results = retrieve_policy_chunks("I cannot log in, getting invalid credentials error", n_results=3)
        sources = [r["metadata"].get("source") for r in results]
        assert "technical_support_guide.md" in sources, (
            f"Expected technical_support_guide.md in top 3, got: {sources}"
        )

    def test_faq_query_returns_support_faq_chunk(self):
        """A general how-to question should surface support_faq.md."""
        results = retrieve_policy_chunks("How do I reset my password?", n_results=3)
        sources = [r["metadata"].get("source") for r in results]
        assert "support_faq.md" in sources, (
            f"Expected support_faq.md in top 3, got: {sources}"
        )

    def test_top_result_distance_is_close(self):
        """With real embeddings the top result should have a low cosine distance (< 0.5)."""
        results = retrieve_policy_chunks("refund request within 30 days", n_results=1)
        assert len(results) == 1
        assert results[0]["distance"] < 0.5, (
            f"Top result distance {results[0]['distance']:.4f} is too high — "
            "check that ingestion used real embeddings"
        )

    def test_different_queries_return_different_top_results(self):
        """A refund query and a technical query should not return the same top chunk."""
        refund_results = retrieve_policy_chunks("I need a refund", n_results=1)
        tech_results = retrieve_policy_chunks("API returns 401 error", n_results=1)
        assert refund_results[0]["id"] != tech_results[0]["id"], (
            "Refund and technical queries returned the same top chunk — "
            "embeddings may still be random (mock)"
        )
