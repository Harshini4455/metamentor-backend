"""Risk model"""
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(20), default="medium")   # low / medium / high / critical
    status: Mapped[str] = mapped_column(String(20), default="open")       # open / resolved / ignored
    related_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    related_member: Mapped[str | None] = mapped_column(String(100), nullable=True)
    suggested_action: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
