import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router, health_router
from src.api.dashboard import router as dashboard_router
from src.api.middleware import RequestLoggingMiddleware
from src.api.auth import require_api_key
from src.observability.logging_config import configure_logging

load_dotenv()
configure_logging()

app = FastAPI(
    title="Operations Performance API",
    description=(
        "Read-only analytics API over the Northstar Manufacturing procurement process. "
        "Wraps the same analytics/ML logic used by the local pipeline and dashboard, so "
        "there's one source of truth for every number -- including for operations-assistant, "
        "which consumes these endpoints as agent tools rather than reimplementing the logic."
    ),
    version="0.1.0",
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    # Comma-separated list of allowed origins, e.g. "https://dashboard.example.com,http://localhost:5173"
    # Falls back to localhost-only if unset, rather than defaulting to "*" -- an analytics API
    # exposing operational data shouldn't be open to any origin by default, even in early dev.
    allow_origins=os.environ.get("API_ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health_router)
# Unauthenticated, same reasoning as operations-assistant's /demo/chat -- a portfolio
# visitor viewing aggregate, non-sensitive analytics shouldn't need an API key.
app.include_router(dashboard_router)
app.include_router(router, dependencies=[Depends(require_api_key)])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
