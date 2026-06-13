"""
Risk Agent
Detects blockers, workload overloads, deadline risks, knowledge gaps.
Uses Gemini to analyze context + triggers AI Negotiation Agent.
"""
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.risk import Risk
from models.team_member import TeamMember
from services.gemini_client import gemini
from core.websocket_manager import ws_manager

RISK_SYSTEM = """You are a Risk Analysis Agent for an engineering team.
Analyze the provided context and return ONLY valid JSON:
{
  "risks": [
    {
      "title": "string",
      "description": "string",
      "severity": "critical|high|medium|low",
      "related_member": "name or null",
      "suggested_action": "string",
      "tags": ["tag1", "tag2"]
    }
  ]
}"""


class RiskAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze(self, meeting_result: dict, task_result: dict) -> dict:
        # Gather workload data
        workloads = await self._get_workloads()
        overloaded = [m for m in workloads if m["workload"] >= 100]

        prompt = f"""
Meeting summary: {meeting_result.get('summary', '')}
Tasks created: {json.dumps(task_result.get('tasks', [])[:5])}
Team workloads: {json.dumps(workloads)}
Overloaded members: {json.dumps(overloaded)}

Identify risks, blockers, and workload conflicts.
"""
        raw = await gemini.generate(prompt, RISK_SYSTEM)

        try:
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(clean)
        except json.JSONDecodeError:
            parsed = {"risks": []}

        saved_risks = []
        for r in parsed.get("risks", []):
            risk = Risk(
                id=str(uuid.uuid4()),
                title=r.get("title", "Unknown Risk"),
                description=r.get("description", ""),
                severity=r.get("severity", "medium"),
                related_member=r.get("related_member"),
                suggested_action=r.get("suggested_action", ""),
                tags=r.get("tags", []),
            )
            self.db.add(risk)
            saved_risks.append({
                "id": risk.id,
                "title": risk.title,
                "severity": risk.severity,
                "suggested_action": risk.suggested_action,
            })

        await self.db.commit()

        # Broadcast risk alerts
        if saved_risks:
            await ws_manager.broadcast_event("risks_detected", {"risks": saved_risks})

        return {"risks_found": len(saved_risks), "risks": saved_risks}

    async def _get_workloads(self) -> list:
        result = await self.db.execute(select(TeamMember))
        members = result.scalars().all()
        return [{"name": m.name, "workload": m.workload_percent, "tasks": m.active_task_count} for m in members]

    async def negotiate_rebalance(self, from_member: str, to_member: str, task_id: str) -> dict:
        """AI Negotiation Agent — moves task and rebalances workload."""
        from models.task import Task
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return {"success": False, "error": "Task not found"}

        old_owner = task.owner
        task.owner = to_member

        await self._update_workload(from_member, -15)
        await self._update_workload(to_member, +15)
        await self.db.commit()

        await ws_manager.broadcast_event("task_reassigned", {
            "task_id": task_id,
            "from": old_owner,
            "to": to_member,
            "reason": "AI Negotiation Agent — workload rebalance",
        })
        return {"success": True, "task_id": task_id, "new_owner": to_member}

    async def _update_workload(self, name: str, delta: int):
        result = await self.db.execute(select(TeamMember).where(TeamMember.name.ilike(f"%{name}%")))
        m = result.scalar_one_or_none()
        if m:
            m.workload_percent = min(150, max(0, m.workload_percent + delta))
            await self.db.commit()
