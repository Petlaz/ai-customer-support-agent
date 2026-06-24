# RAG Architecture

## Overview

The RAG (Retrieval-Augmented Generation) layer provides the agent with relevant policy knowledge at query time. Instead of encoding company policies into the LLM's weights (static, expensive to update), we store them as vector embeddings in ChromaDB and retrieve the most relevant chunks for each incoming ticket. This grounds the agent's responses in current policy text and prevents hallucination.

---

## Pipeline

```
data/policies/*.md
       │
       ▼
document_loader.py      ← loads 4 markdown files as LangChain Documents
       │                   metadata: source, source_path, categories, doc_type
       ▼
text_extractor.py       ← strips markdown headings, bold, links, inline code
       │
       ▼
chunker.py              ← RecursiveCharacterTextSplitter
       │                   CHUNK_SIZE=500 chars, CHUNK_OVERLAP=50 chars
       │                   → 50 chunks from 4 policy files
       ▼
embeddings.py           ← OpenAI text-embedding-3-small (1536 dims)
       │                   fallback: deterministic mock (MD5 hash seed)
       ▼
vector_store.py         ← ChromaDB PersistentClient at data/chroma_db/
       │                   collection: policy_documents
       ▼
retriever.py            ← query_collection(query, n_results=5)
       │
       ▼
metadata_filter.py      ← optional post-retrieval filter by source/category
       │
       ▼
context_formatter.py    ← formats chunks as [Source: filename]\ntext
       │
       ▼
LLM prompt (Phase 7)
```

---

## Files

| File | Responsibility |
|------|---------------|
| `rag/document_loader.py` | Loads all 4 policy `.md` files; `load_documents_for_category(category)` loads only files mapped to that ticket category |
| `rag/text_extractor.py` | Strips markdown syntax (headings, bold, links, code, table separators) before chunking |
| `rag/chunker.py` | Splits documents into 500-char chunks with 50-char overlap; tags each chunk with `chunk_index` |
| `rag/embeddings.py` | `get_embedding(text)` — tries OpenAI first, falls back to mock on `RateLimitError`; mock is deterministic (same text → same vector) |
| `rag/vector_store.py` | `add_documents`, `query_collection`, `delete_collection`; converts list metadata to CSV strings for ChromaDB compatibility |
| `rag/retriever.py` | `retrieve_policy_chunks(query, n)` and `retrieve_similar_tickets(query, n)` — thin wrappers over `query_collection` |
| `rag/metadata_filter.py` | `filter_by_source`, `filter_by_category`, `get_relevant_sources` — post-retrieval filtering |
| `rag/context_formatter.py` | `format_context` — prefixes each chunk with `[Source: filename]` for LLM prompt injection |

---

## Collections

| Collection | Purpose | Documents |
|------------|---------|-----------|
| `policy_documents` | Company policy chunks for grounding responses | 50 chunks from 4 policy files |
| `historical_tickets` | Resolved historical tickets for similar-case retrieval | Populated by Phase 6 memory layer |

---

## Policy Files

| File | Categories |
|------|-----------|
| `data/policies/billing_policy.md` | Billing |
| `data/policies/refund_policy.md` | Refund, Billing |
| `data/policies/technical_support_guide.md` | Technical Support, Account Access, Product Questions |
| `data/policies/support_faq.md` | All categories |

The `CATEGORY_TO_POLICY_FILES` map in `config/constants.py` controls which files are loaded per category via `load_documents_for_category()`.

---

## Embedding Status

| Status | Embedding model | Semantic accuracy |
|--------|----------------|------------------|
| Current | Mock (hash-based unit vector) | Random — retrieval works but results are not semantically ranked |
| After credits | `text-embedding-3-small` (OpenAI) | Full semantic relevance |

To switch to real embeddings: add OpenAI billing credits, then run `delete_collection("policy_documents")` and re-ingest. No code changes required.

---

## Re-ingestion Command

```python
from rag.vector_store import delete_collection, POLICY_COLLECTION, add_documents
from rag.document_loader import load_policy_documents
from rag.chunker import chunk_documents

delete_collection(POLICY_COLLECTION)
docs = load_policy_documents()
chunks = chunk_documents(docs)
count = add_documents(chunks, POLICY_COLLECTION)
print(f"Re-ingested {count} chunks")
```
