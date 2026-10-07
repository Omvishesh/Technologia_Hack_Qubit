"""
Metrics and system load tracking service.
Monitors request throughput, error rate, latency, CPU/memory, and connection pool state.
"""
import time
import os
import psutil
from typing import Dict, Any, List

class MetricsService:
    def __init__(self):
        self.total_requests = 0
        self.total_errors = 0
        self.recent_latencies: List[float] = []
        self.start_time = time.time()
        self.process = psutil.Process(os.getpid())

    def record_request(self, latency_ms: float, is_error: bool = False):
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
        error_rate = (
            round((self.total_errors / self.total_requests) * 100, 2)
            if self.total_requests > 0 else 0.0
        )

        return {
            "uptime_seconds": round(time.time() - self.start_time, 1),
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate_percent": error_rate,
            "avg_latency_ms": avg_latency,
            "active_db_connections": pool_status.get("active_connections", 0),
            "max_db_connections": pool_status.get("max_pool_size", 5),
            "pool_exhausted": pool_status.get("pool_exhausted", False),
            "waiting_requests": pool_status.get("waiting_requests", 0),
        }

    def get_system_load(self) -> Dict[str, Any]:
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
            "active_http_requests": self.total_requests,
        }

metrics_service = MetricsService()

