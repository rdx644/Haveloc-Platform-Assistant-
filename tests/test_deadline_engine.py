import pytest
import datetime
from backend.services.deadline_engine import evaluate_deadline, assert_deadline_valid_for_submission
from backend.schemas import UrgencyLevel

def test_deadline_expired():
    now = datetime.datetime.now(datetime.timezone.utc)
    past_deadline = now - datetime.timedelta(minutes=10)
    report = evaluate_deadline(past_deadline, current_time=now)
    assert report.is_expired is True
    assert report.urgency == UrgencyLevel.EXPIRED
    assert report.seconds_remaining < 0

    with pytest.raises(ValueError, match="expired"):
        assert_deadline_valid_for_submission(past_deadline)

def test_deadline_critical():
    now = datetime.datetime.now(datetime.timezone.utc)
    crit_deadline = now + datetime.timedelta(minutes=45)
    report = evaluate_deadline(crit_deadline, current_time=now)
    assert report.is_expired is False
    assert report.urgency == UrgencyLevel.CRITICAL
    assert report.hours_remaining < 2.0

def test_deadline_urgent():
    now = datetime.datetime.now(datetime.timezone.utc)
    urgent_deadline = now + datetime.timedelta(hours=8)
    report = evaluate_deadline(urgent_deadline, current_time=now)
    assert report.is_expired is False
    assert report.urgency == UrgencyLevel.URGENT
    assert 2.0 <= report.hours_remaining <= 24.0

def test_deadline_normal():
    now = datetime.datetime.now(datetime.timezone.utc)
    normal_deadline = now + datetime.timedelta(days=3)
    report = evaluate_deadline(normal_deadline, current_time=now)
    assert report.is_expired is False
    assert report.urgency == UrgencyLevel.NORMAL
    assert report.hours_remaining > 24.0

def test_string_format_and_timezone():
    iso_deadline = "2026-10-15T18:30:00Z"
    report = evaluate_deadline(iso_deadline)
    assert report.deadline_utc.tzinfo is not None
    assert report.deadline_utc.year == 2026
