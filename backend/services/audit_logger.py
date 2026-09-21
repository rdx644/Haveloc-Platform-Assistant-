import json
import uuid
import re
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.models import ApplicationEvent, utcnow

FORBIDDEN_KEY_PATTERNS = [
    r'password', r'cookie', r'session', r'token', r'secret', r'auth_header'
]

def sanitize_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Redacts sensitive credentials, cookies, and tokens from metadata before logging."""
    sanitized = {}
    for k, v in meta.items():
        k_lower = k.lower()
        if any(re.search(pat, k_lower) for pat in FORBIDDEN_KEY_PATTERNS):
            sanitized[k] = "[REDACTED_BY_SECURITY_POLICY]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_metadata(v)
        elif isinstance(v, str) and len(v) > 200:
            sanitized[k] = v[:200] + "... [TRUNCATED]"
        else:
            sanitized[k] = v
    return sanitized

def log_application_event(
    db: Session,
    application_id: str,
    event_type: str,
    metadata: Optional[Dict[str, Any]] = None
) -> ApplicationEvent:
    """Records an immutable audit event in the application history."""
    clean_meta = sanitize_metadata(metadata or {})
    event = ApplicationEvent(
        id=f"EVT-{uuid.uuid4().hex[:10]}",
        application_id=application_id,
        event_type=event_type,
        timestamp=utcnow(),
        metadata_json=json.dumps(clean_meta)
    )
    db.add(event)
    db.commit()
    return event
