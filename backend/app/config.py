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
    LLM_PROVIDER: str = "gemini" # gemini | openai | mock
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = str(BASE_DIR / "backend" / "logs" / "app.log")

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
