"""
Metrics and system load tracking service.
Monitors request throughput, error rate, latency, CPU/memory, and connection pool state.
"""
import time
import os
from collections import deque
import psutil
from typing import Dict, Any, List, Deque, Tuple

ERROR_WINDOW_SECONDS = 60   # error rate covers only recent requests
ERROR_MIN_SAMPLES = 5       # below this, report 0% (too few requests to judge)

class MetricsService:
    def __init__(self):
        self.total_requests = 0
        self.total_errors = 0
        self.in_flight = 0  # /chat requests being served right now (see middleware in main.py)
        self.recent_outcomes: Deque[Tuple[float, bool]] = deque()  # (timestamp, is_error)
        self.recent_latencies: List[float] = []
        self.start_time = time.time()
        self.process = psutil.Process(os.getpid())

    def record_request(self, latency_ms: float, is_error: bool = False):
        self.recent_outcomes.append((time.time(), is_error))
        self.total_requests += 1
        if is_error:
            self.total_errors += 1
        self.recent_latencies.append(latency_ms)
        if len(self.recent_latencies) > 200:
            self.recent_latencies.pop(0)

    def get_metrics(self, pool_status: Dict[str, Any]) -> Dict[str, Any]:
        avg_latency = (
            round(sum(self.recent_latencies) / len(self.recent_latencies), 2)
            if self.recent_latencies else 0.0
        )
        # Error rate over the last ERROR_WINDOW_SECONDS only, and only with enough samples:
        # a cumulative rate stays high long after an outage and re-triggers incidents.
        now = time.time()
        while self.recent_outcomes and self.recent_outcomes[0][0] < now - ERROR_WINDOW_SECONDS:
            self.recent_outcomes.popleft()
        window = len(self.recent_outcomes)
        window_errors = sum(1 for _, is_error in self.recent_outcomes if is_error)
        error_rate = round(window_errors / window * 100, 2) if window >= ERROR_MIN_SAMPLES else 0.0

        return {
            "uptime_seconds": round(time.time() - self.start_time, 1),
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate_percent": error_rate,
            "error_rate_window_requests": window,
            "avg_latency_ms": avg_latency,
            "active_db_connections": pool_status.get("active_connections", 0),
            "max_db_connections": pool_status.get("max_pool_size", 5),
            "pool_exhausted": pool_status.get("pool_exhausted", False),
            "waiting_requests": pool_status.get("waiting_requests", 0),
        }

    def get_system_load(self, extra_in_flight: int = 0) -> Dict[str, Any]:
        """Current load. `extra_in_flight` adds simulated clients (traffic-surge demo)."""
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            mem_info = self.process.memory_info()
            mem_mb = round(mem_info.rss / (1024 * 1024), 2)
        except Exception:
            cpu_percent = 0.0
            mem_mb = 0.0

        return {
            "cpu_percent": cpu_percent,
            "memory_mb": mem_mb,
            "active_http_requests": self.in_flight + extra_in_flight,  # in progress now, not all-time
            "total_requests": self.total_requests,
        }

metrics_service = MetricsService()

