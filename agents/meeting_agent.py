"""
Meeting Agent
Parses transcripts/documents → extracts decisions, action items, participants.
"""
import json
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from models.meeting import Meeting
from services.gemini_client import gemini


MEETING_SYSTEM = """You are a Meeting Intelligence Agent. 
Parse the input text and return ONLY valid JSON with this exact structure:
{
  "title": "string",
  "summary": "string (2-3 sentences)",
  "decisions": ["decision1", "decision2"],
  "action_items": [
    {"task": "string", "owner": "string", "priority": "critical|high|medium|low", "due_days": 3}
  ],
  "participants": ["name1", "name2"]
}
Extract real names if mentioned. For priority: critical=blocker/urgent, high=this week, medium=this sprint, low=backlog."""


class MeetingAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process(self, content: str, filename: str) -> dict:
        prompt = f"Parse this meeting/document content:\n\n{content[:8000]}"
        raw = await gemini.generate(prompt, MEETING_SYSTEM)

        # Clean and parse JSON
        try:
            # Strip markdown fences if present
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(clean)
        except json.JSONDecodeError:
            parsed = {
                "title": filename,
                "summary": content[:300],
                "decisions": [],
                "action_items": [],
                "participants": [],
            }

        # Persist to DB
        meeting = Meeting(
            id=str(uuid.uuid4()),
            title=parsed.get("title", filename),
            raw_transcript=content,
            summary=parsed.get("summary", ""),
            decisions=parsed.get("decisions", []),
            action_items=parsed.get("action_items", []),
            participants=parsed.get("participants", []),
            processed=True,
        )
        self.db.add(meeting)
        await self.db.commit()
        await self.db.refresh(meeting)

        parsed["meeting_id"] = meeting.id
        return parsed
