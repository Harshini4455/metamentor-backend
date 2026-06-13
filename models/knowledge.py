"""Knowledge Base entry model"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(255), default="")          # filename / meeting title
    source_type: Mapped[str] = mapped_column(String(50), default="meeting")  # meeting / slack / doc
    tags: Mapped[list] = mapped_column(JSON, default=list)
    linked_project: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # ChromaDB doc id
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
