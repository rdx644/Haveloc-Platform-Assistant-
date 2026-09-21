import hmac
import hashlib
import uuid
import datetime
from sqlalchemy.orm import Session
from backend.models import Application, SubmissionAuthorization
from backend.schemas import AuthorizationTokenPayload
from backend.config import settings

def generate_authorization_signature(
    application_id: str,
    application_hash: str,
    expires_at_iso: str
) -> str:
    """Creates a cryptographic HMAC signature for the authorization token."""
    message = f"{application_id}:{application_hash}:{expires_at_iso}".encode("utf-8")
    return hmac.new(settings.HMAC_SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()

def create_submission_authorization(
    db: Session,
    application_id: str
) -> AuthorizationTokenPayload:
    """
    Issues a short-lived submission authorization object for a verified application.
    Requires app.state == 'PRE_SUBMISSION_VERIFIED'.
    """
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise ValueError(f"Application {application_id} not found.")

    if app.state != "PRE_SUBMISSION_VERIFIED":
        raise ValueError(
            f"Cannot authorize submission: Application is in state '{app.state}', "
            f"must be 'PRE_SUBMISSION_VERIFIED'."
        )

    if not app.application_hash:
        raise ValueError("Application hash missing. Verification must be re-run.")

    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(seconds=settings.SUBMISSION_AUTH_TTL_SECONDS)
    sig = generate_authorization_signature(app.id, app.application_hash, expires_at.isoformat())
    auth_token = f"AUTH-{uuid.uuid4().hex[:12]}-{sig[:32]}"

    # Revoke any previous pending authorizations for this application
    db.query(SubmissionAuthorization).filter(
        SubmissionAuthorization.application_id == app.id,
        SubmissionAuthorization.status == "AUTHORIZED"
    ).update({"status": "REVOKED"})

    auth_record = SubmissionAuthorization(
        id=f"AUTH-REC-{uuid.uuid4().hex[:8]}",
        application_id=app.id,
        application_hash=app.application_hash,
        auth_token=auth_token,
        verified_at=now,
        expires_at=expires_at,
        status="AUTHORIZED"
    )
    db.add(auth_record)

    app.state = "SUBMISSION_AUTHORIZED"
    db.commit()

    return AuthorizationTokenPayload(
        auth_token=auth_token,
        application_id=app.id,
        application_hash=app.application_hash,
        expires_at=expires_at,
        ttl_seconds=settings.SUBMISSION_AUTH_TTL_SECONDS,
        status="AUTHORIZED"
    )

def validate_submission_authorization(
    db: Session,
    application_id: str,
    auth_token: str,
    current_application_hash: str
) -> SubmissionAuthorization:
    """
    Validates that the authorization token is valid, matches the current application hash,
    and has not expired or already been consumed.
    """
    auth = (
        db.query(SubmissionAuthorization)
        .filter(
            SubmissionAuthorization.application_id == application_id,
            SubmissionAuthorization.auth_token == auth_token
        )
        .first()
    )

    if not auth:
        raise ValueError("Submission authorization token is invalid or unrecognized.")

    if auth.status != "AUTHORIZED":
        raise ValueError(f"Submission authorization token is no longer active (status: {auth.status}).")

    now = datetime.datetime.now(datetime.timezone.utc)
    # Ensure expires_at is timezone aware
    expires_at_utc = auth.expires_at
    if expires_at_utc.tzinfo is None:
        expires_at_utc = expires_at_utc.replace(tzinfo=datetime.timezone.utc)

    if now > expires_at_utc:
        auth.status = "EXPIRED"
        db.commit()
        raise ValueError("Submission authorization token has expired. Please re-verify application.")

    if auth.application_hash != current_application_hash:
        auth.status = "REVOKED"
        db.commit()
        raise ValueError(
            "Application integrity mismatch: Payload was altered after authorization was granted. "
            "Authorization revoked; pre-submission verification must be repeated."
        )

    return auth
