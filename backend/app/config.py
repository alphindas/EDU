from functools import lru_cache
from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EDUNEST_", extra="ignore")

    # Hosting platforms set plain DATABASE_URL / SECRET_KEY; the EDUNEST_ prefixed names also work.
    database_url: str = Field("sqlite:///./edunest.db", validation_alias=AliasChoices("EDUNEST_DATABASE_URL", "DATABASE_URL"))
    secret_key: str = Field("dev-only-change-me-in-production-please-32b+", validation_alias=AliasChoices("EDUNEST_SECRET_KEY", "SECRET_KEY"))
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    # Exact origins (comma-separated or JSON list) plus a regex for preview/production hosts. Default regex allows any
    # *.pages.dev (Cloudflare Pages); tighten to the exact URL once known. Auth is a bearer token (no cookies), so a
    # broad origin list does not by itself expose sessions.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        ["http://localhost:5173", "http://127.0.0.1:5173"], validation_alias=AliasChoices("EDUNEST_CORS_ORIGINS", "CORS_ORIGINS"))
    cors_origin_regex: str = r"^https://([a-z0-9-]+\.)*pages\.dev$"
    # Create demo school + logins on startup if the DB is empty (for ephemeral demo hosting only).
    seed_demo: bool = Field(False, validation_alias=AliasChoices("EDUNEST_SEED_DEMO", "SEED_DEMO"))

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                return json.loads(v)
            return [x.strip().rstrip("/") for x in v.split(",") if x.strip()]
        return v

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
