"""FastAPI application entry point.

URL layout (identical in dev and behind Apache):
  /api/...  JSON API: /api/items, /api/dicesim (+ OpenAPI docs at /api/docs)
  /ui/...   server-rendered Jinja2 pages
"""

from fastapi import APIRouter, FastAPI
from sqlalchemy import text

from checkout.config import get_settings
from checkout.db import SessionDep
from checkout.routers import dice, items, pages

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

api = APIRouter(prefix="/api")
api.include_router(items.router)
api.include_router(dice.router)


@api.get("/health", tags=["meta"])
def health(session: SessionDep) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


# Routes are copied when included, so include `api` after all its routes are defined.
app.include_router(api)
app.include_router(pages.router)
