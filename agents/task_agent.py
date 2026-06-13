"""
Task Agent
Creates tasks from meeting action items, assigns owners, checks workload.
"""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.task import Task
from models.team_member import TeamMember
from core.websocket_manager import ws_manager


class TaskAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_from_meeting(self, meeting_result: dict) -> dict:
        action_items = meeting_result.get("action_items", [])
        meeting_id = meeting_result.get("meeting_id")
        created_tasks = []

        for item in action_items:
            due = datetime.utcnow() + timedelta(days=item.get("due_days", 7))
            task = Task(
                id=str(uuid.uuid4()),
                title=item.get("task", "Untitled Task"),
                owner=item.get("owner", "Unassigned"),
                priority=item.get("priority", "medium"),
                status="open",
                due_date=due,
                source_meeting_id=meeting_id,
            )
            self.db.add(task)
            created_tasks.append({
                "id": task.id,
                "title": task.title,
                "owner": task.owner,
                "priority": task.priority,
                "due_date": due.isoformat(),
            })

            # Update team member workload
            await self._update_workload(task.owner, +15)

        await self.db.commit()

        # Broadcast new tasks
        await ws_manager.broadcast_event("tasks_created", {"tasks": created_tasks})
        return {"created": len(created_tasks), "tasks": created_tasks}

    async def _update_workload(self, owner_name: str, delta: int):
        result = await self.db.execute(
            select(TeamMember).where(TeamMember.name.ilike(f"%{owner_name}%"))
        )
        member = result.scalar_one_or_none()
        if member:
            member.workload_percent = min(150, max(0, member.workload_percent + delta))
            member.active_task_count += 1
            await self.db.commit()
