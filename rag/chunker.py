"""Splits LangChain Documents into smaller overlapping chunks for embedding and retrieval."""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.constants import CHUNK_OVERLAP, CHUNK_SIZE


def chunk_documents(documents: list[Document]) -> list[Document]:
    """Split documents into chunks using recursive character splitting.

    Preserves source metadata on every chunk so retrieval results can be
    traced back to the originating policy file.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    # Tag each chunk with its position for debugging / traceability
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i

    return chunks


def chunk_texts(texts: list[str], metadatas: list[dict] | None = None) -> list[Document]:
    """Split raw strings into Document chunks, optionally attaching metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    metadatas = metadatas or [{} for _ in texts]
    return splitter.create_documents(texts, metadatas=metadatas)
