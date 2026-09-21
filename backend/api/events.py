from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models import ApplicationEvent

router = APIRouter(prefix="/events", tags=["Events & Audit"])

@router.get("")
def list_recent_events(limit: int = 50, db: Session = Depends(get_db)):
    events = (
        db.query(ApplicationEvent)
        .order_by(ApplicationEvent.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "application_id": e.application_id,
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "metadata": e.get_metadata()
        }
        for e in events
    ]

@router.get("/application/{app_id}")
def get_application_events(app_id: str, db: Session = Depends(get_db)):
    events = (
        db.query(ApplicationEvent)
        .filter(ApplicationEvent.application_id == app_id)
        .order_by(ApplicationEvent.timestamp.asc())
        .all()
    )
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "metadata": e.get_metadata()
        }
        for e in events
    ]
