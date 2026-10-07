"""
Structured JSON logging module for student-api service.
Writes machine-readable JSON logs to backend/logs/app.log and console.
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from backend.app.config import settings

log_file_path = Path(settings.LOG_FILE_PATH)
log_file_path.parent.mkdir(parents=True, exist_ok=True)

class StructuredJsonLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path

    def _format_timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def log_event(
        self,
        endpoint: str,
        status: int,
        request_id: str = "req-default",
        user_query: Optional[str] = None,
        generated_sql: Optional[str] = None,
        db_pool_active: int = 0,
        db_pool_max: int = 5,
        latency_ms: float = 0.0,
        error: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        record = {
            "timestamp": self._format_timestamp(),
            "service": "student-api",
            "request_id": request_id,
            "endpoint": endpoint,
            "user_query": user_query,
            "generated_sql": generated_sql,
            "db_pool_active": db_pool_active,
            "db_pool_max": db_pool_max,
            "status": status,
            "error": error,
            "latency_ms": round(latency_ms, 2),
        }
        if extra:
            record.update(extra)

        line = json.dumps(record)

        # Print to stdout for docker log collection
        print(line, flush=True)

        # Append to persistent log file
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            print(f"[LOGGER ERROR] Failed writing log to {self.log_path}: {e}", file=sys.stderr)

    def read_logs(self, limit: int = 100, level: Optional[str] = None, status: Optional[int] = None):
        if not self.log_path.exists():
            return []
        lines = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if status and entry.get("status") != status:
                        continue
                    lines.append(entry)
                except Exception:
                    continue
        return lines[-limit:]

logger = StructuredJsonLogger(log_file_path)
