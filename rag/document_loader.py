"""Loads policy documents from disk and returns LangChain Document objects with source metadata."""
from pathlib import Path

from langchain_core.documents import Document

from config.constants import CATEGORY_TO_POLICY_FILES

POLICY_DIR = Path("data/policies")

# Reverse map: filename -> list of categories that reference it
_FILE_TO_CATEGORIES: dict[str, list[str]] = {}
for _category, _files in CATEGORY_TO_POLICY_FILES.items():
    for _filename in _files:
        _FILE_TO_CATEGORIES.setdefault(_filename, []).append(_category)


def load_policy_documents() -> list[Document]:
    """Load all policy markdown files and return as LangChain Documents."""
    documents: list[Document] = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        documents.append(
            Document(
                page_content=text,
                metadata={
                    "source": path.name,
                    "source_path": str(path),
                    "categories": _FILE_TO_CATEGORIES.get(path.name, []),
                    "doc_type": "policy",
                },
            )
        )
    return documents


def load_documents_for_category(category: str) -> list[Document]:
    """Load only the policy documents relevant to a specific ticket category."""
    documents: list[Document] = []
    for filename in CATEGORY_TO_POLICY_FILES.get(category, []):
        path = POLICY_DIR / filename
        if path.exists():
            text = path.read_text(encoding="utf-8")
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": filename,
                        "source_path": str(path),
                        "categories": [category],
                        "doc_type": "policy",
                    },
                )
            )
    return documents
