"""Login and logout pages (/ui/login, /ui/logout)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, Response

from checkout.auth import (
    CurrentUserOptional,
    SessionToken,
    clear_session_cookie,
    is_safe_next,
    require_csrf,
    set_session_cookie,
)
from checkout.db import SessionDep
from checkout.sessions import authenticate, end_session, start_session
from checkout.templating import templates

router = APIRouter(prefix="/ui", include_in_schema=False)

# Deliberately vague: "unknown user" vs "wrong password" would tell an attacker which names exist.
LOGIN_FAILED = "Invalid username or password."


@router.get("/login", name="login_page")
def login_page(
    request: Request, current_user: CurrentUserOptional, next: str | None = None
) -> Response:
    context = {"current_user": current_user, "username": "", "error": None, "next": next}
    return templates.TemplateResponse(request, "login.html", context)


@router.post("/login", name="login")
def login(
    request: Request,
    db: SessionDep,
    old_token: SessionToken = None,
    username: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    next: Annotated[str | None, Form()] = None,
) -> Response:
    user = authenticate(db, username, password)
    if user is None:
        context = {"current_user": None, "username": username, "error": LOGIN_FAILED, "next": next}
        return templates.TemplateResponse(
            request, "login.html", context, status_code=status.HTTP_401_UNAUTHORIZED
        )

    token, _ = start_session(db, user, replaces=old_token)
    # Back to the page that sent us here, but only if it's on this site (see is_safe_next).
    target = next if is_safe_next(next) else str(request.url_for("items_page"))
    response = RedirectResponse(target, status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, token)
    return response


# Login can't check a CSRF token (there's no session yet); the app-wide Sec-Fetch-Site check
# and SameSite cover it. Logout can, so it does.
@router.post("/logout", name="logout", dependencies=[Depends(require_csrf)])
def logout(request: Request, db: SessionDep, token: SessionToken = None) -> Response:
    if token:
        end_session(db, token)  # the row is gone, so a copied cookie is useless from now on
    response = RedirectResponse(request.url_for("login_page"), status.HTTP_303_SEE_OTHER)
    clear_session_cookie(response)
    return response
