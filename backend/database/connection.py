"""
Database connection pool and state manager for student-api backend.
Supports connection pooling, health checks, execution, and failure simulation.
"""
import time
import threading
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool, StaticPool
from backend.app.config import settings

class DatabaseManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.engine = None
        self.is_exhausted = False
        self.is_unavailable = False
        self.synthetic_delay_seconds = 0.0
        self.force_invalid_sql = False
        self._held_connections = []
        self._waiting_requests = 0
        self._active_connections = 0
        self._init_engine()

    def _init_engine(self):
        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite"):
            # QueuePool over SQLite for testing pool exhaustion
            self.engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                connect_args={"check_same_thread": False},
            )
        else:
            # PostgreSQL connection pool
            self.engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT,
            )

    def execute_query(self, query_str: str) -> List[Dict[str, Any]]:
        """
        Executes a SQL query against the database using connection pool.
        Throws appropriate exceptions when simulated failures are active.
        """
        if self.is_unavailable:
            raise ConnectionError("Database connection refused: PostgreSQL host unreachable on port 5432.")

        if self.synthetic_delay_seconds > 0:
            time.sleep(self.synthetic_delay_seconds)

        if self.is_exhausted:
            # Simulate pool timeout waiting for connection
            with self._lock:
                self._waiting_requests += 1
            try:
                time.sleep(settings.DB_POOL_TIMEOUT)
                raise TimeoutError(
                    f"PoolTimeoutError: Timeout waiting for connection from pool after {settings.DB_POOL_TIMEOUT}s "
                    f"(active: {settings.DB_POOL_SIZE}/{settings.DB_POOL_SIZE})"
                )
            finally:
                with self._lock:
                    self._waiting_requests = max(0, self._waiting_requests - 1)

        with self._lock:
            self._active_connections += 1

        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query_str))
                if result.returns_rows:
                    columns = result.keys()
                    rows = [dict(zip(columns, row)) for row in result.fetchall()]
                    return rows
                conn.commit()
                return []
        finally:
            with self._lock:
                self._active_connections = max(0, self._active_connections - 1)

    def exhaust_pool(self, count: Optional[int] = None):
        """Simulate DB Connection Pool Exhaustion incident."""
        with self._lock:
            self.is_exhausted = True
            # Lease actual connections until pool is saturated
            if not self._held_connections:
                target = count or settings.DB_POOL_SIZE
                for _ in range(target):
                    try:
                        conn = self.engine.connect()
                        self._held_connections.append(conn)
                    except Exception:
                        break

    def clear_pool(self):
        """Allowlisted remediation: Reset pool and release all held connections."""
        with self._lock:
            self.is_exhausted = False
            self.is_unavailable = False
            self.synthetic_delay_seconds = 0.0
            self.force_invalid_sql = False
            self._waiting_requests = 0
            self._active_connections = 0

            for conn in self._held_connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._held_connections.clear()

        # Re-initialize engine
        if self.engine:
            try:
                self.engine.dispose()
            except Exception:
                pass
        self._init_engine()

    def set_unavailable(self, status: bool = True):
        self.is_unavailable = status

    def set_delay(self, seconds: float):
        self.synthetic_delay_seconds = seconds

    def set_force_invalid_sql(self, status: bool = True):
        self.force_invalid_sql = status

    def get_pool_status(self) -> Dict[str, Any]:
        """Returns connection pool metrics for Om's verification tools."""
        current_active = len(self._held_connections) + self._active_connections
        return {
            "active_connections": min(current_active, settings.DB_POOL_SIZE),
            "max_pool_size": settings.DB_POOL_SIZE,
            "waiting_requests": self._waiting_requests,
            "pool_exhausted": self.is_exhausted or (current_active >= settings.DB_POOL_SIZE),
        }

    def check_health(self) -> Dict[str, Any]:
        """Pings DB to verify connectivity."""
        start_t = time.time()
        try:
            if self.is_unavailable:
                return {
                    "db_reachable": False,
                    "ping_latency_ms": 0.0,
                    "can_query": False,
                    "error": "ConnectionRefusedError: Host unreachable"
                }
            if self.is_exhausted:
                return {
                    "db_reachable": True,
                    "ping_latency_ms": round((time.time() - start_t) * 1000, 2),
                    "can_query": False,
                    "error": "PoolTimeoutError: Active pool exhausted"
                }
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1;"))
            ping_ms = round((time.time() - start_t) * 1000, 2)
            return {
                "db_reachable": True,
                "ping_latency_ms": ping_ms,
                "can_query": True,
                "error": None
            }
        except Exception as e:
            return {
                "db_reachable": False,
                "ping_latency_ms": round((time.time() - start_t) * 1000, 2),
                "can_query": False,
                "error": str(e)
            }

db_manager = DatabaseManager()
