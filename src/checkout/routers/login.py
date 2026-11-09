"""Login and logout pages (/ui/login, /ui/logout)."""

from typing import Annotated

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse, Response

from checkout.auth import (
    CurrentUserOptional,
    SessionToken,
    clear_session_cookie,
    is_safe_next,
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

    if old_token:  # logging in again (e.g. as someone else) replaces the previous session
        end_session(db, old_token)
    # Always a brand-new token after login, never one the browser had before
    # (otherwise an attacker could plant a known token: "session fixation").
    token = start_session(db, user)
    # Back to the page that sent us here, but only if it's on this site (see is_safe_next).
    target = next if is_safe_next(next) else str(request.url_for("new_item_page"))
    response = RedirectResponse(target, status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, token)
    return response


@router.post("/logout", name="logout")
def logout(request: Request, db: SessionDep, token: SessionToken = None) -> Response:
    if token:
        end_session(db, token)  # the row is gone, so a copied cookie is useless from now on
    response = RedirectResponse(request.url_for("login_page"), status.HTTP_303_SEE_OTHER)
    clear_session_cookie(response)
    return response
