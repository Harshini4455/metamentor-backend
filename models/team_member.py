"""Team Member model"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(200), default="", unique=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    workload_percent: Mapped[int] = mapped_column(Integer, default=0)     # 0–150
    avatar_initials: Mapped[str] = mapped_column(String(3), default="??")
    active_task_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
