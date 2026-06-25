"""Agent performance metrics endpoint."""
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from database.models import AgentLog
from database.session import get_db

router = APIRouter()


@router.get("/", summary="Agent performance metrics")
def get_metrics(db: Session = Depends(get_db)):
    """Return aggregate statistics from the agent_logs table."""
    total = db.query(func.count(AgentLog.id)).scalar() or 0
    escalations = (
        db.query(func.count(AgentLog.id))
        .filter(AgentLog.escalation_required.is_(True))
        .scalar() or 0
    )
    avg_conf = db.query(func.avg(AgentLog.confidence_score)).scalar() or 0.0
    total_tokens = db.query(func.sum(AgentLog.tokens_used)).scalar() or 0
    total_cost = db.query(func.sum(AgentLog.cost_usd)).scalar() or 0.0

    # Tickets per classification
    by_class = (
        db.query(AgentLog.classification, func.count(AgentLog.id))
        .filter(AgentLog.classification.isnot(None))
        .group_by(AgentLog.classification)
        .all()
    )

    return {
        "total_tickets_processed": total,
        "total_escalations": escalations,
        "escalation_rate": round(escalations / total, 4) if total > 0 else 0.0,
        "average_confidence_score": round(float(avg_conf), 4),
        "total_tokens_used": int(total_tokens),
        "total_cost_usd": round(float(total_cost), 6),
        "tickets_by_classification": {row[0]: row[1] for row in by_class},
    }
