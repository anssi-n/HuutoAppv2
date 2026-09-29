from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from prometheus_client import make_asgi_app
from auth import PageAuthRedirect
from db import engine
from routers import items_route, users_route, ui_route, task_log_route, config_route, health_route
from redis_queue import redis_client # type: ignore
from logger import LoggingConfigListener
from prometheus_middleware import MetricsMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    await redis_client.connect()
    LoggingConfigListener.start_listener()
    yield
    # Shutdown
    await engine.dispose()
    await redis_client.disconnect() 
    LoggingConfigListener.stop_listener()

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

app.add_middleware(MetricsMiddleware)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

app.include_router(users_route.router, prefix="/api/v1/users", tags=["users"])
app.include_router(items_route.router, prefix="/api/v1/items", tags=["items"])
app.include_router(config_route.router, prefix="/api/v1/config", tags=["config"])
app.include_router(task_log_route.router, prefix="/api/v1/task_log", tags=["task_log"])
app.include_router(health_route.router, prefix="/health", tags=["health"])
app.include_router(ui_route.router, prefix="", tags=["ui"])


@app.exception_handler(PageAuthRedirect)
async def page_auth_redirect(_request: Request, exc: PageAuthRedirect) -> RedirectResponse:
    """Send an unauthenticated page navigation back to the UI, which explains
    the problem and offers the sign-in dialog, instead of a raw JSON body."""
    return RedirectResponse(url=exc.url, status_code=status.HTTP_303_SEE_OTHER)