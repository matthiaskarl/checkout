"""FastAPI application entry point.

URL layout (identical in dev and behind Apache):
  /api/...  JSON API: /api/items, /api/dicesim, /api/session (+ OpenAPI docs at /api/docs)
  /ui/...   server-rendered Jinja2 pages (incl. /ui/login, /ui/logout)
"""

from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from checkout.auth import LoginRequired, reject_cross_site_requests
from checkout.config import get_settings
from checkout.db import SessionDep
from checkout.routers import dice, items, login, pages, session_api

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    # App-wide: applies to every route, including /ui/login and anything added later.
    dependencies=[Depends(reject_cross_site_requests)],
)

api = APIRouter(prefix="/api")
api.include_router(items.router)
api.include_router(dice.router)
api.include_router(session_api.router)


@api.get("/health", tags=["meta"])
def health(session: SessionDep) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


# Routes are copied when included, so include `api` after all its routes are defined.
app.include_router(api)
app.include_router(pages.router)
app.include_router(login.router)


@app.exception_handler(LoginRequired)
def redirect_to_login(request: Request, exc: LoginRequired) -> RedirectResponse:
    url = request.url_for("login_page").include_query_params(next=exc.next_url)
    return RedirectResponse(url, status.HTTP_303_SEE_OTHER)
