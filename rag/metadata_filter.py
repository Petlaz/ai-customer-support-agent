"""Filters ChromaDB retrieval results by source file or ticket category metadata."""
from config.constants import CATEGORY_TO_POLICY_FILES


def filter_by_source(results: list[dict], source_filename: str) -> list[dict]:
    """Keep only results whose source metadata matches the given filename."""
    return [r for r in results if r.get("metadata", {}).get("source") == source_filename]


def filter_by_category(results: list[dict], category: str) -> list[dict]:
    """Keep only results whose categories metadata includes the given category."""
    filtered = []
    for r in results:
        cats = r.get("metadata", {}).get("categories", "")
        # categories stored as comma-separated string in ChromaDB
        cat_list = [c.strip() for c in cats.split(",")] if isinstance(cats, str) else cats
        if category in cat_list:
            filtered.append(r)
    return filtered


def get_relevant_sources(category: str) -> list[str]:
    """Return the list of policy filenames relevant to a ticket category."""
    return CATEGORY_TO_POLICY_FILES.get(category, [])
