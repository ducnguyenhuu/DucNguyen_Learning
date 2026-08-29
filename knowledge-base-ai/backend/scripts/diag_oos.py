"""Check OOS query similarity scores against corpus."""
from __future__ import annotations
import asyncio
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from app.providers.factory import create_embedding_provider
from app.db.vector_store import VectorStore


async def main() -> None:
    emb = create_embedding_provider()
    store = VectorStore()
    oos_queries = [
        "How do I bake a chocolate cake?",
        "What is the current Tesla stock price?",
        "Who won the 2022 FIFA World Cup?",
        "What is the weather like in Paris today?",
        "Tell me a joke about programmers.",
        "What year was the Eiffel Tower built?",
        "Explain quantum entanglement.",
        "Give me a recipe for pasta carbonara.",
        "What is the capital of Australia?",
        "How do I change a car tire?",
    ]
    for q in oos_queries:
        vec = await emb.embed(q)
        col = store._ensure_connected()
        result = col.query(
            query_embeddings=[vec],
            n_results=1,
            include=["metadatas", "distances"],
        )
        if result["distances"] and result["distances"][0]:
            dist = result["distances"][0][0]
            score = 1.0 - dist
            meta = result["metadatas"][0][0]
            print(f"  score={score:.4f}  best={meta.get('file_name','?')}  {q[:60]}")
        else:
            print(f"  No result for: {q[:60]}")


if __name__ == "__main__":
    asyncio.run(main())
