from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram
import time
from functools import wraps

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["app_name", "method", "endpoint", "http_status"]
)

REQUEST_DURATION = Histogram(
    "request_duration_seconds",
    "Request duration in seconds",
    ["app_name", "method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

TASK_DURATION = Histogram(
    "task_duration_seconds",
    "Task duration in seconds",
    ["app_name", "task_name"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 15.0, 20.0]
)

def task_latency(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            duration = time.time() - start_time
            TASK_DURATION.labels(app_name="huutoworker", task_name=func.__qualname__).observe(duration)
    return wrapper

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):

        if request.url.path.startswith("/metrics"):
            return await call_next(request)

        method = request.method
        endpoint = request.url.path

        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as _:
            status_code = 500
            raise
        finally:
            # Record duration
            duration = time.time() - start_time
            REQUEST_DURATION.labels(app_name="huutoapp", method=method, endpoint=endpoint).observe(duration)

            # Record request count
            REQUEST_COUNT.labels(
                app_name="huutoapp",
                method=method,
                endpoint=endpoint,
                http_status=str(status_code)
            ).inc()

        return response