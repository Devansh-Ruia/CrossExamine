"""Document ingestion pipeline for CrossExamine.

Takes uploaded files, chunks them with LlamaIndex, builds a vector index.
Uses local HuggingFace embeddings (BAAI/bge-small-en-v1.5) to avoid
needing a third API key.

Key design: we use LlamaIndex for retrieval only. We grab the raw nodes
and pass them to our own Claude call. We do NOT use LlamaIndex's built-in
synthesizer or response generation.
"""

import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# Initialize embedding model once at module level.
# First run downloads the model (~130MB). Subsequent runs use cache.
_embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
RETRIEVAL_TOP_K = 5


def ingest_documents(
    file_paths: list[str],
) -> tuple[VectorStoreIndex, list[str], dict[str, dict]]:
    """Chunk documents and build a vector index.

    Returns:
        index: VectorStoreIndex for retrieval
        source_filenames: list of original filenames (for citation detection)
        chunk_store: {node_id: {text, metadata}} for all chunks
    """
    reader = SimpleDirectoryReader(input_files=file_paths)
    documents = reader.load_data()

    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    nodes = splitter.get_nodes_from_documents(documents)

    for i, node in enumerate(nodes):
        meta = node.metadata
        page_ref = _get_page_ref(meta, i)
        meta["page_ref"] = page_ref

    index = VectorStoreIndex(nodes, embed_model=_embed_model)

    source_filenames = list(
        {os.path.basename(fp) for fp in file_paths}
    )

    chunk_store = {}
    for node in nodes:
        chunk_store[node.node_id] = {
            "text": node.text,
            "metadata": dict(node.metadata),
        }

    return index, source_filenames, chunk_store


def _get_page_ref(metadata: dict, chunk_index: int) -> str:
    """Extract page reference from metadata with fallback chain.
    Uses page_label if PDF provides it, otherwise estimates from chunk index,
    otherwise gives up gracefully. Never confidently says 'page 0'."""
    page_label = metadata.get("page_label")
    if page_label and page_label != "0":
        return f"p. {page_label}"

    estimated_page = (chunk_index // 3) + 1
    if estimated_page > 1:
        return f"approx. p. {estimated_page}"

    return "approx. page unknown"


def retrieve_chunks(
    index: VectorStoreIndex, query: str, top_k: int = RETRIEVAL_TOP_K
) -> list[dict]:
    """Retrieve top-k chunks for a query. Returns raw nodes with scores.
    Does NOT use LlamaIndex's synthesizer."""
    retriever = index.as_retriever(similarity_top_k=top_k)
    results = retriever.retrieve(query)

    chunks = []
    for node_with_score in results:
        node = node_with_score.node
        chunks.append(
            {
                "id": node.node_id,
                "text": node.text,
                "metadata": dict(node.metadata),
                "score": node_with_score.score,
            }
        )
    return chunks


def chunks_above_threshold(chunks: list[dict], threshold: float = 0.3) -> bool:
    """Returns True if ANY chunk scores above the threshold."""
    return any(c["score"] >= threshold for c in chunks)


def format_chunk_for_context(chunk: dict) -> str:
    """Format a retrieved chunk for inclusion in an agent's context."""
    meta = chunk["metadata"]
    file_name = meta.get("file_name", "unknown")
    page_ref = meta.get("page_ref", "unknown")
    score = chunk.get("score", 0)
    return (
        f"[Source: {file_name}, {page_ref} | relevance: {score:.2f}]\n"
        f"{chunk['text']}"
    )
