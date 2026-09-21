import datetime
from typing import Optional, Union
from backend.schemas import DeadlineReport, UrgencyLevel
from backend.config import settings

def ensure_utc(dt: Union[datetime.datetime, str]) -> datetime.datetime:
    """Ensure datetime is converted to timezone-aware UTC."""
    if isinstance(dt, str):
        # Support ISO formats
        if dt.endswith("Z"):
            dt = dt[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(dt)
    
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    return dt

def evaluate_deadline(
    deadline: Union[datetime.datetime, str],
    current_time: Optional[datetime.datetime] = None
) -> DeadlineReport:
    """
    Deterministic calculation of time remaining and urgency classification.
    Strict rule: Never relies on LLMs for temporal evaluations.
    """
    if current_time is None:
        current_time_utc = datetime.datetime.now(datetime.timezone.utc)
    else:
        current_time_utc = ensure_utc(current_time)

    deadline_utc = ensure_utc(deadline)
    delta = deadline_utc - current_time_utc
    seconds_remaining = delta.total_seconds()
    hours_remaining = seconds_remaining / 3600.0

    if seconds_remaining <= 0:
        is_expired = True
        urgency = UrgencyLevel.EXPIRED
        formatted = "Deadline Expired"
    elif hours_remaining < settings.DEADLINE_CRITICAL_HOURS:
        is_expired = False
        urgency = UrgencyLevel.CRITICAL
        mins = int(seconds_remaining // 60)
        formatted = f"{mins} minutes remaining (CRITICAL)"
    elif hours_remaining <= settings.DEADLINE_URGENT_HOURS:
        is_expired = False
        urgency = UrgencyLevel.URGENT
        hrs = int(hours_remaining)
        mins = int((seconds_remaining % 3600) // 60)
        formatted = f"{hrs}h {mins}m remaining (URGENT)"
    else:
        is_expired = False
        urgency = UrgencyLevel.NORMAL
        days = int(hours_remaining // 24)
        hrs = int(hours_remaining % 24)
        formatted = f"{days}d {hrs}h remaining"

    return DeadlineReport(
        deadline_utc=deadline_utc,
        current_time_utc=current_time_utc,
        seconds_remaining=seconds_remaining,
        hours_remaining=hours_remaining,
        is_expired=is_expired,
        urgency=urgency,
        formatted_time_remaining=formatted
    )

def assert_deadline_valid_for_submission(deadline: Union[datetime.datetime, str]) -> None:
    """
    Re-check the deadline immediately before submission.
    Raises ValueError if expired.
    """
    report = evaluate_deadline(deadline)
    if report.is_expired:
        raise ValueError(
            f"Submission rejected: Application deadline has expired at {report.deadline_utc.isoformat()}."
        )
