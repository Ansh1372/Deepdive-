import time
import uuid
from collections import defaultdict
from threading import Lock


class MetricsTracker:
    """Simple in-memory metrics for observability."""

    def __init__(self):
        self._lock = Lock()
        self.total_requests = 0
        self.total_errors = 0
        self.total_chats = 0
        self.total_ingests = 0
        self.response_times = []  # last 100
        self.pipeline_step_times = defaultdict(list)  # step_name -> [times]

    def record_request(self):
        with self._lock:
            self.total_requests += 1

    def record_error(self):
        with self._lock:
            self.total_errors += 1

    def record_chat(self, response_time: float):
        with self._lock:
            self.total_chats += 1
            self.response_times.append(response_time)
            if len(self.response_times) > 100:
                self.response_times = self.response_times[-100:]

    def record_ingest(self):
        with self._lock:
            self.total_ingests += 1

    def record_pipeline_step(self, step_name: str, duration: float):
        with self._lock:
            self.pipeline_step_times[step_name].append(duration)
            if len(self.pipeline_step_times[step_name]) > 50:
                self.pipeline_step_times[step_name] = self.pipeline_step_times[step_name][-50:]

    def get_metrics(self) -> dict:
        with self._lock:
            avg_response = (
                sum(self.response_times) / len(self.response_times)
                if self.response_times else 0
            )

            pipeline_avgs = {}
            for step, times in self.pipeline_step_times.items():
                pipeline_avgs[step] = round(sum(times) / len(times), 3) if times else 0

            return {
                "total_requests": self.total_requests,
                "total_chats": self.total_chats,
                "total_ingests": self.total_ingests,
                "total_errors": self.total_errors,
                "avg_response_time_s": round(avg_response, 3),
                "p95_response_time_s": round(
                    sorted(self.response_times)[int(len(self.response_times) * 0.95)]
                    if self.response_times else 0, 3
                ),
                "pipeline_avg_times": pipeline_avgs,
            }


def generate_request_id() -> str:
    """Generate a short unique request ID for tracing."""
    return uuid.uuid4().hex[:8]


# Global singleton
metrics = MetricsTracker()
