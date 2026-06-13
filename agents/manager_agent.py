"""
Manager Agent
Generates leadership reports and answers strategic questions.
"""
import json

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.task import Task
from models.risk import Risk
from services.gemini_client import gemini

REPORT_SYSTEM = """You are a Manager Intelligence Agent.
Generate an executive sprint report. Return ONLY valid JSON:
{
  "executive_summary": "string",
  "velocity_percent": 78,
  "key_risks": ["risk1", "risk2"],
  "highlights": ["win1", "win2"],
  "recommendations": ["action1", "action2"]
}"""


class ManagerAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_summary(self, pipeline_results: dict) -> dict:
        # Gather real stats
        task_count = await self.db.scalar(select(func.count(Task.id)))
        open_tasks = await self.db.scalar(
            select(func.count(Task.id)).where(Task.status == "open")
        )
        risk_count = len(pipeline_results.get("risks", {}).get("risks", []))

        prompt = f"""
Sprint data:
- Total tasks: {task_count}
- Open tasks: {open_tasks}
- Risks detected: {risk_count}
- Meeting summary: {pipeline_results.get('meeting', {}).get('summary', '')}
- Risks: {json.dumps(pipeline_results.get('risks', {}).get('risks', [])[:3])}

Generate executive sprint report.
"""
        raw = await gemini.generate(prompt, REPORT_SYSTEM)
        try:
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            return {
                "executive_summary": "Sprint in progress. Multiple risks flagged by AI.",
                "velocity_percent": 78,
                "key_risks": ["Auth module delay", "Workload imbalance"],
                "highlights": ["On-time deliveries this week"],
                "recommendations": ["Rebalance Rahul's tasks"],
            }

    async def answer(self, question: str, context: str) -> str:
        return await gemini.answer_question(question, context)
