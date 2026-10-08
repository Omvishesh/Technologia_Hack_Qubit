"""
Centralized configuration for the Incident Response System.

Loads settings from the project-level .env file and exposes them
as a typed Pydantic Settings object.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


# Resolve project root (parent of incident-response/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All incident-response configuration, loaded from .env."""

    # ── General ──────────────────────────────────────────────
    env: str = Field("development", alias="ENV")
    debug: str = Field("True", alias="DEBUG")

    @property
    def is_debug(self) -> bool:
        """Parse debug as bool, tolerating non-boolean values like 'release'."""
        return self.debug.lower() in ("true", "1", "yes")

    # ── Service Endpoints ────────────────────────────────────
    backend_url: str = Field("http://localhost:8000", alias="BACKEND_URL")
    incident_service_host: str = Field("0.0.0.0", alias="INCIDENT_SERVICE_HOST")
    incident_service_port: int = Field(8001, alias="INCIDENT_SERVICE_PORT")
    incident_service_url: str = Field("http://localhost:8001", alias="INCIDENT_SERVICE_URL")

    # ── LLM ──────────────────────────────────────────────────
    llm_provider: str = Field("groq", alias="LLM_PROVIDER")
    groq_api_key: str = Field("", alias="GROQ_API_KEY")
    groq_model: str = Field("llama-3.3-70b-versatile", alias="GROQ_MODEL")
    nvidia_api_key: str = Field("", alias="NVIDIA_API_KEY")
    nvidia_model: str = Field("meta/llama-3.1-70b-instruct", alias="NVIDIA_MODEL")
    nvidia_base_url: str = Field("https://integrate.api.nvidia.com/v1", alias="NVIDIA_BASE_URL")
    # Failover keys — order: Groq #1 -> #2 -> #3 -> NVIDIA #1 -> #2 -> #3
    groq_api_key_2: str = Field("", alias="GROQ_API_KEY_2")
    groq_api_key_3: str = Field("", alias="GROQ_API_KEY_3")
    nvidia_api_key_2: str = Field("", alias="NVIDIA_API_KEY_2")
    nvidia_api_key_3: str = Field("", alias="NVIDIA_API_KEY_3")
    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    llm_model: str = Field("llama-3.3-70b-versatile", alias="LLM_MODEL")

    # ── Incident Detection ───────────────────────────────────
    detector_interval_seconds: int = Field(5, alias="DETECTOR_INTERVAL_SECONDS")
    error_rate_threshold: float = Field(0.5, alias="ERROR_RATE_THRESHOLD")
    max_hypotheses: int = Field(3, alias="MAX_HYPOTHESES")
    # Consecutive failed health/metrics polls before the detector raises an incident
    health_failures_before_incident: int = Field(2, alias="HEALTH_FAILURES_BEFORE_INCIDENT")

    # ── Log Monitor Agent (tails the student-api log file) ───
    log_monitor_enabled: bool = Field(True, alias="LOG_MONITOR_ENABLED")
    log_monitor_interval_seconds: float = Field(1.0, alias="LOG_MONITOR_INTERVAL_SECONDS")
    log_window_seconds: int = Field(60, alias="LOG_WINDOW_SECONDS")
    # Failures of unknown kind / slow requests needed in the window before raising
    log_error_threshold: int = Field(2, alias="LOG_ERROR_THRESHOLD")
    log_slow_request_ms: float = Field(6000, alias="LOG_SLOW_REQUEST_MS")

    # ── Logging ──────────────────────────────────────────────
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_file_path: str = Field("backend/logs/app.log", alias="LOG_FILE_PATH")

    # ── Email / SMTP ─────────────────────────────────────────
    devops_email: str = Field("devops-engineer@hackqubit.local", alias="DEVOPS_EMAIL")
    smtp_host: str = Field("smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_username: str = Field("", alias="SMTP_USERNAME")
    smtp_password: str = Field("", alias="SMTP_PASSWORD")
    smtp_from: str = Field("incident-system@hackqubit.local", alias="SMTP_FROM")
    email_mock_mode: bool = Field(True, alias="EMAIL_MOCK_MODE")

    # ── Phone alert (ntfy push notification) ─────────────────
    ntfy_server: str = Field("https://ntfy.sh", alias="NTFY_SERVER")
    ntfy_topic: str = Field("", alias="NTFY_TOPIC")   # empty = phone alerts off

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",          # ignore vars we don't define
        "populate_by_name": True,    # allow both alias and field name
    }


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()

