"""
Agent Orchestrator
Coordinates: MeetingAgent → TaskAgent → KnowledgeAgent → RiskAgent → ManagerAgent
Broadcasts real-time progress over WebSocket.
"""
import asyncio
from typing import Optional

from core.websocket_manager import ws_manager
from agents.meeting_agent import MeetingAgent
from agents.task_agent import TaskAgent
from agents.knowledge_agent import KnowledgeAgent
from agents.risk_agent import RiskAgent
from agents.manager_agent import ManagerAgent


class AgentOrchestrator:
    def __init__(self, db_session, client_id: Optional[str] = None):
        self.db = db_session
        self.client_id = client_id
        self.meeting_agent = MeetingAgent(db_session)
        self.task_agent = TaskAgent(db_session)
        self.knowledge_agent = KnowledgeAgent(db_session)
        self.risk_agent = RiskAgent(db_session)
        self.manager_agent = ManagerAgent(db_session)

    async def _emit(self, event: str, data: dict):
        """Broadcast progress event to WebSocket clients."""
        msg = {"type": event, "data": data}
        if self.client_id:
            await ws_manager.send_personal(msg, self.client_id)
        else:
            await ws_manager.broadcast(msg)

    async def process_document(self, content: str, filename: str, doc_type: str) -> dict:
        """
        Main pipeline: document → all 5 agents → consolidated results.
        Each step emits real-time events.
        """
        await self._emit("pipeline_start", {"filename": filename, "doc_type": doc_type})

        results = {}

        # ── Step 1: Meeting Agent ──────────────────────────────────────────────
        await self._emit("agent_start", {"agent": "meeting", "step": 1})
        try:
            meeting_result = await self.meeting_agent.process(content, filename)
            results["meeting"] = meeting_result
            await self._emit("agent_done", {
                "agent": "meeting",
                "step": 1,
                "result": meeting_result,
            })
        except Exception as e:
            await self._emit("agent_error", {"agent": "meeting", "error": str(e)})
            raise

        # ── Step 2: Task Agent ─────────────────────────────────────────────────
        await self._emit("agent_start", {"agent": "task", "step": 2})
        try:
            task_result = await self.task_agent.create_from_meeting(meeting_result)
            results["tasks"] = task_result
            await self._emit("agent_done", {
                "agent": "task",
                "step": 2,
                "result": task_result,
            })
        except Exception as e:
            await self._emit("agent_error", {"agent": "task", "error": str(e)})

        # ── Step 3: Knowledge Agent ────────────────────────────────────────────
        await self._emit("agent_start", {"agent": "knowledge", "step": 3})
        try:
            kb_result = await self.knowledge_agent.store_meeting(meeting_result, filename)
            results["knowledge"] = kb_result
            await self._emit("agent_done", {
                "agent": "knowledge",
                "step": 3,
                "result": kb_result,
            })
        except Exception as e:
            await self._emit("agent_error", {"agent": "knowledge", "error": str(e)})

        # ── Step 4: Risk Agent ─────────────────────────────────────────────────
        await self._emit("agent_start", {"agent": "risk", "step": 4})
        try:
            risk_result = await self.risk_agent.analyze(meeting_result, results.get("tasks", {}))
            results["risks"] = risk_result
            await self._emit("agent_done", {
                "agent": "risk",
                "step": 4,
                "result": risk_result,
            })
        except Exception as e:
            await self._emit("agent_error", {"agent": "risk", "error": str(e)})

        # ── Step 5: Manager Agent ──────────────────────────────────────────────
        await self._emit("agent_start", {"agent": "manager", "step": 5})
        try:
            report_result = await self.manager_agent.generate_summary(results)
            results["report"] = report_result
            await self._emit("agent_done", {
                "agent": "manager",
                "step": 5,
                "result": report_result,
            })
        except Exception as e:
            await self._emit("agent_error", {"agent": "manager", "error": str(e)})

        await self._emit("pipeline_complete", {"results": results})
        return results
