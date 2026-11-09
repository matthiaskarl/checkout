"""The shared Jinja2 environment for all HTML routers."""

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates


def _csrf_context(request: Request) -> dict[str, Any]:
    """Every template gets `csrf_token`, so forms only need
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">."""
    login = getattr(request.state, "login_session", None)  # set by checkout.auth
    return {"csrf_token": login.csrf_token if login else ""}


templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent / "templates",
    context_processors=[_csrf_context],  # run for every TemplateResponse
)
