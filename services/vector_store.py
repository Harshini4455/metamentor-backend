"""ChromaDB vector store — semantic search for knowledge base."""
import uuid
from typing import List, Optional

from core.config import settings


class VectorStore:
    def __init__(self):
        self.collection = None
        self._init()

    def _init(self):
        try:
            import chromadb
            client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
            self.collection = client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            # Graceful fallback — in-memory stub
            self.collection = None

    async def add(self, doc_id: str, text: str, metadata: dict) -> bool:
        if not self.collection:
            return True  # No-op if ChromaDB not running
        try:
            self.collection.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata],
            )
            return True
        except Exception:
            return False

    async def query(self, query_text: str, n_results: int = 5) -> List[dict]:
        if not self.collection:
            return []
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
            out = []
            for i, doc in enumerate(results["documents"][0]):
                out.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i],
                    "score": 1 - results["distances"][0][i],
                })
            return out
        except Exception:
            return []

    async def delete(self, doc_id: str):
        if self.collection:
            try:
                self.collection.delete(ids=[doc_id])
            except Exception:
                pass


vector_store = VectorStore()
