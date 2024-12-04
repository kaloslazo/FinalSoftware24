import time
import logging
import statistics
from typing import Dict, List

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ServiceMonitor:
    def __init__(self, window_size: int = 3600):
        self.window_size = window_size
        self.requests: List[Dict] = []
        self.total_requests = 0
        self.failed_requests = 0
        self._metrics_cache = {}
        self._last_cache_time = 0
        self._cache_ttl = 1

    def _clean_old_requests(self):
        current_time = time.time()
        cutoff_time = current_time - self.window_size
        self.requests = [r for r in self.requests if r["timestamp"] > cutoff_time]

    def record_request(self, duration: float, success: bool):
        current_time = time.time()
        is_error = not success and duration > 0.001
        
        self.requests.append({
            "timestamp": current_time,
            "duration": duration,
            "success": success,
            "is_error": is_error
        })
        
        self.total_requests += 1
        if is_error:
            self.failed_requests += 1
        
        self._metrics_cache = {}

    def get_metrics(self) -> Dict:
        current_time = time.time()
        if self._metrics_cache and (current_time - self._last_cache_time) < self._cache_ttl:
            return self._metrics_cache.copy()

        self._clean_old_requests()
        
        if not self.requests:
            return {
                "availability": 100.0,
                "reliability": 100.0,
                "avg_response_time": 0,
                "total_requests": 0,
                "failed_requests": 0,
                "requests_last_hour": 0,
                "latency_p95": 0
            }

        recent_requests = [r for r in self.requests if r["timestamp"] > (current_time - 300)]
        
        if recent_requests:
            successful_requests = sum(1 for r in recent_requests if r["success"])
            availability = (successful_requests / len(recent_requests)) * 100
            
            durations = [r["duration"] for r in recent_requests]
            avg_duration = statistics.mean(durations)
            
            # Calcular el percentil 95 de latencia
            sorted_durations = sorted(durations)
            p95_index = int(len(sorted_durations) * 0.95)
            latency_p95 = sorted_durations[p95_index] if p95_index < len(sorted_durations) else sorted_durations[-1]
            
            reliability = sum(1 for d in durations if d < 0.001) / len(durations) * 100
        else:
            availability = 100.0
            reliability = 100.0
            avg_duration = 0
            latency_p95 = 0

        metrics = {
            "availability": availability,
            "reliability": reliability,
            "avg_response_time": avg_duration,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "requests_last_hour": len(self.requests),
            "latency_p95": latency_p95
        }

        self._metrics_cache = metrics.copy()
        self._last_cache_time = current_time
        
        return metrics