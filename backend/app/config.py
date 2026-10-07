"""
Configuration management for Student Chatbot Backend API.
Loads configurations from environment variables or .env file.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    ENV: str = "development"
    DEBUG: bool = True

    # Server config
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 3000

    # Inter-service URLs
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    INCIDENT_SERVICE_URL: str = "http://localhost:8001"

    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'database' / 'students.db'}"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 0
    DB_POOL_TIMEOUT: float = 3.0

    # LLM Settings
    PRIMARY_LLM_PROVIDER: str = "groq"
    FALLBACK_LLM_PROVIDER: str = "nvidia"

    # Groq (Primary)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Failover keys — order: Groq #1 -> #2 -> #3 -> NVIDIA #1 -> #2 -> #3
    GROQ_API_KEY_2: str = ""
    GROQ_API_KEY_3: str = ""

    # NVIDIA NIM (Fallback)
    NVIDIA_API_KEY: str = ""
    NVIDIA_API_KEY_2: str = ""
    NVIDIA_API_KEY_3: str = ""
    NVIDIA_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Legacy / Optional
    LLM_PROVIDER: str = "groq"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "qwen/qwen3.8-27b"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = str(BASE_DIR / "backend" / "logs" / "app.log")

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

