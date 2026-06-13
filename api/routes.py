"""
All API routes for MetaMentor.
Prefix: /api/v1
"""
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.websocket_manager import ws_manager
from models.task import Task
from models.meeting import Meeting
from models.risk import Risk
from models.knowledge import KnowledgeEntry
from models.team_member import TeamMember
from services.agent_orchestrator import AgentOrchestrator
from services.gemini_client import gemini
from agents.risk_agent import RiskAgent
from agents.knowledge_agent import KnowledgeAgent

router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    owner: str
    priority: str = "medium"
    due_date: Optional[str] = None

class TaskUpdate(BaseModel):
    status: Optional[str] = None
    owner: Optional[str] = None
    priority: Optional[str] = None

class QuestionRequest(BaseModel):
    question: str

class RebalanceRequest(BaseModel):
    from_member: str
    to_member: str
    task_id: str

class TeamMemberCreate(BaseModel):
    name: str
    role: str
    email: str
    skills: list[str] = []


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get("/dashboard/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    total_tasks = await db.scalar(select(func.count(Task.id))) or 0
    open_tasks = await db.scalar(select(func.count(Task.id)).where(Task.status == "open")) or 0
    risk_count = await db.scalar(select(func.count(Risk.id)).where(Risk.status == "open")) or 0
    kb_count = await db.scalar(select(func.count(KnowledgeEntry.id))) or 0
    meeting_count = await db.scalar(select(func.count(Meeting.id))) or 0

    return {
        "total_tasks": total_tasks,
        "open_tasks": open_tasks,
        "at_risk": risk_count,
        "kb_entries": kb_count,
        "meetings_processed": meeting_count,
    }


# ── Upload & Process ───────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    client_id: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    allowed = {".txt", ".pdf", ".md", ".json", ".csv"}
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed:
        raise HTTPException(400, f"File type {ext} not supported. Use: {allowed}")

    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = content_bytes.decode("latin-1")

    # Determine document type
    doc_type = "meeting" if any(w in content.lower()[:500] for w in ["meeting", "standup", "discussed", "agreed", "action"]) else "document"

    orchestrator = AgentOrchestrator(db, client_id=client_id or None)
    results = await orchestrator.process_document(content, file.filename, doc_type)
    return {"status": "success", "filename": file.filename, "results": results}


# ── Tasks ──────────────────────────────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).order_by(desc(Task.created_at)))
    tasks = result.scalars().all()
    return [
        {
            "id": t.id, "title": t.title, "owner": t.owner,
            "priority": t.priority, "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]

@router.post("/tasks")
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db)):
    task = Task(
        id=str(uuid.uuid4()),
        title=body.title,
        owner=body.owner,
        priority=body.priority,
        status="open",
        due_date=datetime.fromisoformat(body.due_date) if body.due_date else None,
    )
    db.add(task)
    await db.commit()
    await ws_manager.broadcast_event("task_created", {"task": {"id": task.id, "title": task.title, "owner": task.owner}})
    return {"id": task.id, "status": "created"}

@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    if body.status:
        task.status = body.status
    if body.owner:
        task.owner = body.owner
    if body.priority:
        task.priority = body.priority
    await db.commit()
    await ws_manager.broadcast_event("task_updated", {"task_id": task_id, "changes": body.model_dump(exclude_none=True)})
    return {"status": "updated"}

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    await db.delete(task)
    await db.commit()
    return {"status": "deleted"}


# ── Risks ──────────────────────────────────────────────────────────────────────

@router.get("/risks")
async def list_risks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Risk).where(Risk.status == "open").order_by(desc(Risk.created_at))
    )
    risks = result.scalars().all()
    return [
        {
            "id": r.id, "title": r.title, "description": r.description,
            "severity": r.severity, "related_member": r.related_member,
            "suggested_action": r.suggested_action, "tags": r.tags,
            "created_at": r.created_at.isoformat(),
        }
        for r in risks
    ]

@router.post("/risks/{risk_id}/resolve")
async def resolve_risk(risk_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Risk).where(Risk.id == risk_id))
    risk = result.scalar_one_or_none()
    if not risk:
        raise HTTPException(404, "Risk not found")
    risk.status = "resolved"
    await db.commit()
    await ws_manager.broadcast_event("risk_resolved", {"risk_id": risk_id})
    return {"status": "resolved"}

@router.post("/risks/rebalance")
async def rebalance_workload(body: RebalanceRequest, db: AsyncSession = Depends(get_db)):
    agent = RiskAgent(db)
    result = await agent.negotiate_rebalance(body.from_member, body.to_member, body.task_id)
    return result


# ── Knowledge Base ─────────────────────────────────────────────────────────────

@router.get("/knowledge")
async def list_knowledge(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(KnowledgeEntry).order_by(desc(KnowledgeEntry.created_at)).limit(50)
    )
    entries = result.scalars().all()
    return [
        {
            "id": e.id, "title": e.title, "source": e.source,
            "source_type": e.source_type, "tags": e.tags,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]

@router.get("/knowledge/search")
async def search_knowledge(q: str, db: AsyncSession = Depends(get_db)):
    agent = KnowledgeAgent(db)
    results = await agent.semantic_search(q)
    return {"results": results}


# ── Ask AI ─────────────────────────────────────────────────────────────────────

@router.post("/ask")
async def ask_ai(body: QuestionRequest, db: AsyncSession = Depends(get_db)):
    # Build context from DB
    task_result = await db.execute(select(Task).where(Task.status == "open").limit(10))
    tasks = task_result.scalars().all()
    risk_result = await db.execute(select(Risk).where(Risk.status == "open").limit(5))
    risks = risk_result.scalars().all()
    member_result = await db.execute(select(TeamMember))
    members = member_result.scalars().all()

    context = f"""
Team members: {', '.join(f"{m.name} ({m.role}, {m.workload_percent}% workload)" for m in members)}
Open tasks: {', '.join(f"{t.title} → {t.owner} [{t.priority}]" for t in tasks[:8])}
Active risks: {', '.join(f"{r.title} [{r.severity}]" for r in risks[:5])}
"""
    answer = await gemini.answer_question(body.question, context)
    return {"answer": answer}


# ── Team ───────────────────────────────────────────────────────────────────────

@router.get("/team")
async def list_team(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TeamMember))
    members = result.scalars().all()
    return [
        {
            "id": m.id, "name": m.name, "role": m.role, "email": m.email,
            "skills": m.skills, "workload_percent": m.workload_percent,
            "active_task_count": m.active_task_count,
            "avatar_initials": m.avatar_initials,
        }
        for m in members
    ]

@router.post("/team")
async def create_member(body: TeamMemberCreate, db: AsyncSession = Depends(get_db)):
    initials = "".join(p[0].upper() for p in body.name.split()[:2])
    member = TeamMember(
        id=str(uuid.uuid4()),
        name=body.name,
        role=body.role,
        email=body.email,
        skills=body.skills,
        workload_percent=0,
        avatar_initials=initials,
    )
    db.add(member)
    await db.commit()
    return {"id": member.id, "status": "created"}


# ── Reports ────────────────────────────────────────────────────────────────────

@router.get("/reports/sprint")
async def get_sprint_report(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count(Task.id))) or 0
    open_t = await db.scalar(select(func.count(Task.id)).where(Task.status == "open")) or 0
    done_t = await db.scalar(select(func.count(Task.id)).where(Task.status == "done")) or 0
    critical_risks = await db.scalar(
        select(func.count(Risk.id)).where(Risk.severity == "critical", Risk.status == "open")
    ) or 0
    velocity = round((done_t / total * 100) if total > 0 else 78)

    risk_result = await db.execute(select(Risk).where(Risk.status == "open").limit(5))
    risks = risk_result.scalars().all()

    member_result = await db.execute(select(TeamMember))
    members = member_result.scalars().all()

    return {
        "velocity_percent": velocity,
        "total_tasks": total,
        "open_tasks": open_t,
        "done_tasks": done_t,
        "critical_risks": critical_risks,
        "executive_summary": f"Sprint velocity at {velocity}%. {len(risks)} active risks. {done_t} tasks completed.",
        "key_risks": [r.title for r in risks],
        "team_workloads": [
            {"name": m.name, "workload": m.workload_percent} for m in members
        ],
        "recommendations": [
            r.suggested_action for r in risks if r.suggested_action
        ],
    }


# ── Seed data (dev) ────────────────────────────────────────────────────────────

@router.post("/seed")
async def seed_demo_data(db: AsyncSession = Depends(get_db)):
    """Populate DB with demo data for hackathon demo."""
    # Team members
    members_data = [
        {"name": "Rahul Kapoor", "role": "Backend Engineer", "email": "rahul@team.com",
         "skills": ["Node.js", "Auth", "PostgreSQL"], "workload_percent": 120, "avatar_initials": "RK"},
        {"name": "Priya Sharma", "role": "Product Designer", "email": "priya@team.com",
         "skills": ["Figma", "UX", "Interviews"], "workload_percent": 72, "avatar_initials": "PS"},
        {"name": "Sam Johnson", "role": "Full Stack Engineer", "email": "sam@team.com",
         "skills": ["React", "Python", "APIs"], "workload_percent": 85, "avatar_initials": "SJ"},
    ]
    for m in members_data:
        existing = await db.scalar(select(TeamMember).where(TeamMember.email == m["email"]))
        if not existing:
            db.add(TeamMember(id=str(uuid.uuid4()), active_task_count=3, **m))

    # Tasks
    tasks_data = [
        {"title": "Fix auth token expiry bug", "owner": "Rahul Kapoor", "priority": "critical", "status": "open"},
        {"title": "Design new user onboarding flow", "owner": "Priya Sharma", "priority": "medium", "status": "open"},
        {"title": "Update API documentation for v2", "owner": "Sam Johnson", "priority": "low", "status": "open"},
        {"title": "Sprint review presentation prep", "owner": "Priya Sharma", "priority": "medium", "status": "open"},
        {"title": "Write unit tests for payment module", "owner": "Sam Johnson", "priority": "low", "status": "open"},
        {"title": "Interview candidate for backend role", "owner": "Rahul Kapoor", "priority": "medium", "status": "open"},
        {"title": "Finalize Q2 OKR retrospective doc", "owner": "Priya Sharma", "priority": "low", "status": "open"},
    ]
    for t in tasks_data:
        db.add(Task(id=str(uuid.uuid4()), created_at=datetime.utcnow(),
                    due_date=datetime(2026, 6, 10), **t))

    # Risks
    risks_data = [
        {"title": "Project Titan delayed by 4 days",
         "description": "Auth module dependency unresolved. Blocking payment flow and user profile.",
         "severity": "critical", "related_member": "Rahul Kapoor",
         "suggested_action": "Reassign 1 task from Rahul to Priya to unblock auth.",
         "tags": ["missing dependency", "resource overload"]},
        {"title": "Rahul workload at 120%",
         "description": "Interview task conflicts with auth bug deadline.",
         "severity": "high", "related_member": "Rahul Kapoor",
         "suggested_action": "Move Interview Candidate task to Priya (72% capacity).",
         "tags": ["overload"]},
        {"title": "Knowledge gap — no standup for 3 days",
         "description": "Team has not logged standup updates, causing context drift.",
         "severity": "medium", "related_member": None,
         "suggested_action": "Enforce daily async standup check-in.",
         "tags": ["knowledge gap"]},
    ]
    for r in risks_data:
        db.add(Risk(id=str(uuid.uuid4()), status="open", created_at=datetime.utcnow(), **r))

    # KB entries
    kb_data = [
        {"title": "Auth Strategy — JWT Refresh Tokens", "content": "Decided in sprint review Jun 3: Use JWT refresh tokens for all auth flows.", "source": "sprint-review-june.txt", "source_type": "meeting", "tags": ["decision", "auth"]},
        {"title": "New Onboarding Flow Requirements", "content": "Priya to lead redesign. Must reduce steps from 7 to 3. Mobile-first.", "source": "design-meeting-may30.txt", "source_type": "meeting", "tags": ["design", "onboarding"]},
        {"title": "API v2 Breaking Changes", "content": "v2 removes XML support. All endpoints return JSON only. Auth header renamed.", "source": "api-planning-doc.pdf", "source_type": "doc", "tags": ["api", "v2"]},
    ]
    for k in kb_data:
        db.add(KnowledgeEntry(id=str(uuid.uuid4()), created_at=datetime.utcnow(), **k))

    await db.commit()
    return {"status": "seeded", "message": "Demo data loaded successfully"}
