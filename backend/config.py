import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Haveloc Placement Application Agent"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Storage
    DATABASE_URL: str = "sqlite:///./placement_agent.db"
    
    # Deterministic Deadline Thresholds (Hours)
    DEADLINE_CRITICAL_HOURS: float = 2.0
    DEADLINE_URGENT_HOURS: float = 24.0
    
    # Pre-submission Authorization token time-to-live in seconds (10 minutes)
    SUBMISSION_AUTH_TTL_SECONDS: int = 600
    
    # Cryptographic Secret for Authorization Verification Token Signing
    HMAC_SECRET_KEY: str = "haveloc-super-secure-deterministic-secret-key-2026"
    
    # Central Portal API Keys & Services
    MOCK_PORTAL_URL: str = "http://localhost:8080"
    BACKEND_PORT: int = 8000
    
    # LLM Settings (Optional fallback to deterministic heuristic synthesis)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
