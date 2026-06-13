"""
Gemini 2.5 client wrapper.
Falls back to demo stubs on quota errors, network failures, or missing API key.
"""
import asyncio
import json

from core.config import settings


class GeminiClient:
    def __init__(self):
        self.model = None
        self._init_model()

    def _init_model(self):
        if not settings.GOOGLE_API_KEY:
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
        except ImportError:
            pass

    async def generate(self, prompt: str, system: str = "") -> str:
        if self.model:
            try:
                full_prompt = f"{system}\n\n{prompt}" if system else prompt
                response = await asyncio.to_thread(
                    self.model.generate_content, full_prompt
                )
                return response.text
            except Exception as e:
                # Quota exceeded, network error, or any API failure → fall back to stub
                print(f"[GeminiClient] API error — falling back to demo mode: {e.__class__.__name__}")
        # ── Demo stub (no key OR API failed) ──────────────────────────────────
        return self._stub_response(prompt)

    def _stub_response(self, prompt: str) -> str:
        """Realistic demo JSON — works without any API key or when quota is hit."""
        p = prompt.lower()
        if "extract" in p or "transcript" in p or "parse" in p or "meeting" in p:
            return json.dumps({
                "summary": "Team discussed sprint goals, auth bug, and onboarding redesign. Project Titan is delayed due to auth module dependency. Rahul is overloaded.",
                "decisions": [
                    "Use JWT refresh tokens with 7-day expiry for all auth flows",
                    "Priya takes over the Friday backend candidate interview from Rahul",
                    "Redis config must be completed by Sam before EOD today",
                    "New onboarding flow approved — reduces steps from 7 to 3",
                ],
                "action_items": [
                    {"task": "Fix auth token expiry bug in production", "owner": "Rahul", "priority": "critical", "due_days": 2},
                    {"task": "Finalize Redis configuration", "owner": "Sam", "priority": "high", "due_days": 1},
                    {"task": "Design new user onboarding flow", "owner": "Priya", "priority": "medium", "due_days": 4},
                    {"task": "Update API documentation for v2", "owner": "Sam", "priority": "medium", "due_days": 5},
                    {"task": "Write unit tests for payment module", "owner": "Sam", "priority": "low", "due_days": 7},
                    {"task": "Conduct backend candidate interview", "owner": "Priya", "priority": "medium", "due_days": 3},
                    {"task": "Escalate Project Titan delay to stakeholders", "owner": "Divya", "priority": "high", "due_days": 1},
                ],
                "participants": ["Rahul Kapoor", "Priya Sharma", "Sam Johnson", "Divya"],
                "title": "Sprint 15 Planning Meeting",
            })
        if "risk" in p:
            return json.dumps({
                "risks": [
                    {
                        "title": "Project Titan delayed by 4 days",
                        "description": "Auth module dependency unresolved. Blocking payment flow and user profile modules downstream.",
                        "severity": "critical",
                        "related_member": "Rahul Kapoor",
                        "suggested_action": "Reassign 1 task from Rahul to unblock auth module. Escalate to stakeholders.",
                        "tags": ["missing dependency", "resource overload"],
                    },
                    {
                        "title": "Rahul workload at 120%",
                        "description": "Interview task conflicts with critical auth bug deadline. High burnout risk.",
                        "severity": "high",
                        "related_member": "Rahul Kapoor",
                        "suggested_action": "Move Interview Candidate task to Priya (72% capacity, has interview skills).",
                        "tags": ["overload"],
                    },
                    {
                        "title": "Sam has no standup updates for 2 days",
                        "description": "Possible silent blocker on Redis config. No Slack mentions or task comments detected.",
                        "severity": "medium",
                        "related_member": "Sam Johnson",
                        "suggested_action": "Async check-in with Sam today to surface any hidden blockers.",
                        "tags": ["silent blocker", "knowledge gap"],
                    },
                ]
            })
        if "report" in p or "summary" in p or "sprint" in p:
            return json.dumps({
                "executive_summary": "Sprint 15 velocity at 78%. 3 active blockers detected by Risk Agent. Auth bug is critical path for Project Titan.",
                "velocity_percent": 78,
                "key_risks": [
                    "Project Titan: 4-day delay due to auth dependency",
                    "Rahul overloaded at 120% — reassignment needed",
                    "Sam silent blocker suspected",
                ],
                "highlights": [
                    "Priya completed onboarding design 2 days early",
                    "Sam shipped API v2 documentation ahead of schedule",
                    "Knowledge base grew by 18 entries this sprint",
                ],
                "recommendations": [
                    "Rebalance Rahul → Priya: Interview task (1-click available)",
                    "Daily async standup check-in required for Sam",
                    "Escalate Project Titan auth delay to stakeholders today",
                ],
            })
        return json.dumps({"result": "processed", "content": prompt[:200]})

    async def answer_question(self, question: str, context: str) -> str:
        if self.model:
            try:
                prompt = f"""You are MetaMentor AI — a team intelligence assistant.
Context about the team:
{context}

Question: {question}

Answer concisely with specific facts. If workload or risk data is available, reference it."""
                response = await asyncio.to_thread(self.model.generate_content, prompt)
                return response.text
            except Exception as e:
                print(f"[GeminiClient] API error in answer_question — demo mode: {e.__class__.__name__}")

        # Demo answers keyed by topic
        answers = {
            "risk":     "🔴 Project Titan delayed 4 days — auth module unresolved, blocking payment flow and user profile. 🟡 Rahul at 120% workload — reassignment recommended. 🟡 Sam: possible silent blocker (no updates 2 days).",
            "overload": "Rahul Kapoor is at 120% capacity with 4 active tasks. AI Negotiation Agent recommends moving the 'Interview Candidate' task to Priya (currently 72% capacity, has interview skills).",
            "titan":    "Root cause: Auth token module incomplete (owner: Rahul, overloaded at 120%). Blocking: Payment flow, User profile. Suggested fix: Reassign 1 task from Rahul to unblock the auth module immediately.",
            "report":   "Sprint 15: Velocity 78%. Open tasks: 24, Blockers: 3 critical. Highlights: Priya shipped design early, Sam completed API docs. Action needed: Rahul workload rebalance.",
            "meeting":  "Last meeting (Sprint 15 Planning, Jun 4): ✅ JWT refresh tokens decided. ✅ Priya to own onboarding redesign. ✅ Sam to update API v2 docs. ✅ Priya taking Friday interview from Rahul.",
            "auth":     "Auth module owned by Rahul Kapoor (Backend Engineer). Status: In progress, 4 days overdue. Workload: 120% — this is causing the delay. Blocking: Project Titan payment flow.",
            "block":    "3 blocked items: (1) Payment flow — waiting on Rahul's auth fix. (2) User profile — same dependency. (3) Redis config — Sam investigating.",
            "workload": "Rahul: 120% 🔴 | Sam: 85% 🟡 | Priya: 72% 🟢. AI recommends moving Rahul's Interview task to Priya to restore balance.",
        }
        q_lower = question.lower()
        for key, ans in answers.items():
            if key in q_lower:
                return ans
        return (
            f"Based on current team data: I found context related to '{question}'. "
            "Key findings: Project Titan is delayed (auth dependency), Rahul is overloaded at 120%, "
            "and 3 active risks are flagged. Check the Risk Radar for detailed analysis and one-click rebalancing."
        )


gemini = GeminiClient()
