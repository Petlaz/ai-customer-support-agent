"""Extracts clean plain text from LangChain Documents, stripping markdown formatting."""
import re

from langchain_core.documents import Document


def extract_text(document: Document) -> str:
    """Return clean plain text from a Document, stripping common markdown syntax."""
    text = document.page_content
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)   # headings
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)           # bold/italic
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)             # underscores
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)              # links
    text = re.sub(r"`(.+?)`", r"\1", text)                        # inline code
    text = re.sub(r"^-{3,}\s*$", "", text, flags=re.MULTILINE)   # hr
    text = re.sub(r"^\|[-|\s]+\|\s*$", "", text, flags=re.MULTILINE)  # table separators
    text = re.sub(r"\n{3,}", "\n\n", text)                        # excess blank lines
    return text.strip()


def extract_texts(documents: list[Document]) -> list[str]:
    """Extract clean text from a list of Documents."""
    return [extract_text(doc) for doc in documents]
