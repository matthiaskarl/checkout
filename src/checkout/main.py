"""FastAPI application entry point."""

from fastapi import FastAPI
from sqlalchemy import text

from checkout.config import get_settings
from checkout.db import SessionDep
from checkout.routers import items

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(items.router)


@app.get("/health", tags=["meta"])
def health(session: SessionDep) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
