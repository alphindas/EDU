from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EDUNEST_", extra="ignore")

    database_url: str = "sqlite:///./edunest.db"
    secret_key: str = "dev-only-change-me-in-production-please-32b+"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # OTP (parents). "dev" provider logs the code and always accepts dev_otp_code.
    otp_provider: str = "dev"
    dev_otp_code: str = "000000"
    otp_ttl_minutes: int = 5
    otp_max_attempts: int = 5
    bcrypt_rounds: int = 12

    # Vision microservice (Phase 2 bridge)
    vision_url: str = "http://localhost:5000"
    vision_token: str = ""
    vision_timeout_seconds: float = 5.0

    # Uploaded files (timetable images, homework, leave attachments). Stored outside the web root, served via auth.
    upload_dir: str = "./uploads"
    max_upload_mb: int = 8

    # AI question generation. "stub" = offline deterministic PDF parser (no model call).
    llm_provider: str = "stub"

    # Phase 4 AI (tutor / chat / flashcards / embeddings). "stub" = offline deterministic implementation, no external call.
    ai_provider: str = "stub"
    ai_daily_limit: int = 100  # AI calls per user per UTC day (cached robo answers don't count)
    ai_max_doc_chars: int = 200_000

    # Teachers may (re)mark attendance this many days back; admins may correct any past date.
    teacher_backdate_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
