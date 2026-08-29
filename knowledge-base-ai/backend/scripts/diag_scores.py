"""Diagnostic script: show raw ChromaDB similarity scores for in-scope queries."""
from __future__ import annotations
import asyncio
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from app.providers.factory import create_embedding_provider
from app.db.vector_store import VectorStore


async def main() -> None:
    emb = create_embedding_provider()
    store = VectorStore()

    queries = [
        "What is the cutting width of SpeedBot 3000?",
        "Who founded TechNova Inc.?",
        "What is PEP 8 recommendation for line length?",
        "What is the goal of Project Atlas?",
        "What is the difference between supervised and unsupervised learning?",
    ]

    for q in queries:
        vec = await emb.embed(q)
        col = store._ensure_connected()
        result = col.query(
            query_embeddings=[vec],
            n_results=3,
            include=["documents", "metadatas", "distances"],
        )
        print(f"\nQuery: {q[:70]}")
        if result["distances"] and result["distances"][0]:
            for dist, meta in zip(result["distances"][0], result["metadatas"][0]):
                score = 1.0 - dist
                fname = meta.get("file_name", "unknown")
                print(f"  score={score:.4f}  dist={dist:.4f}  file={fname}")
        else:
            print("  No results")


if __name__ == "__main__":
    asyncio.run(main())
