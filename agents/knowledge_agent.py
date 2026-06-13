"""
Knowledge Agent
Stores meeting context in PostgreSQL + ChromaDB for semantic retrieval.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from models.knowledge import KnowledgeEntry
from services.vector_store import vector_store


class KnowledgeAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def store_meeting(self, meeting_result: dict, filename: str) -> dict:
        entries_created = []

        # Store summary as KB entry
        if meeting_result.get("summary"):
            entry = await self._store_entry(
                title=meeting_result.get("title", "Meeting Summary"),
                content=meeting_result["summary"],
                source=filename,
                source_type="meeting",
                tags=["summary"],
            )
            entries_created.append(entry)

        # Store each decision
        for decision in meeting_result.get("decisions", []):
            entry = await self._store_entry(
                title=f"Decision: {decision[:80]}",
                content=decision,
                source=filename,
                source_type="meeting",
                tags=["decision"],
            )
            entries_created.append(entry)

        return {"entries_created": len(entries_created), "entries": entries_created}

    async def store_document(self, title: str, content: str, filename: str, doc_type: str = "doc") -> dict:
        chunks = self._chunk_text(content, chunk_size=500)
        entries = []
        for i, chunk in enumerate(chunks):
            entry = await self._store_entry(
                title=f"{title} (part {i+1})",
                content=chunk,
                source=filename,
                source_type=doc_type,
                tags=["document", f"chunk_{i}"],
            )
            entries.append(entry)
        return {"entries_created": len(entries)}

    async def _store_entry(self, title: str, content: str, source: str, source_type: str, tags: list) -> dict:
        doc_id = str(uuid.uuid4())
        entry = KnowledgeEntry(
            id=doc_id,
            title=title,
            content=content,
            source=source,
            source_type=source_type,
            tags=tags,
            embedding_id=doc_id,
        )
        self.db.add(entry)
        await self.db.commit()

        # Store in ChromaDB for semantic search
        await vector_store.add(
            doc_id=doc_id,
            text=f"{title}\n{content}",
            metadata={"source": source, "type": source_type, "title": title},
        )
        return {"id": doc_id, "title": title}

    async def semantic_search(self, query: str, n_results: int = 5) -> list:
        return await vector_store.query(query, n_results)

    def _chunk_text(self, text: str, chunk_size: int = 500) -> list:
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunks.append(" ".join(words[i:i + chunk_size]))
        return chunks or [text]
