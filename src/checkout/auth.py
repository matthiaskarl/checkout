"""HTTP side of authentication: the session cookie and FastAPI dependencies."""

from typing import Annotated, TypeGuard
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, HTTPException, Request, Response, status

from checkout.db import SessionDep
from checkout.models import User
from checkout.sessions import SESSION_LIFETIME, user_for_token

SESSION_COOKIE = "session"


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,  # JavaScript can't read it -> an XSS bug can't steal the session
        secure=True,  # only sent over HTTPS (browsers make an exception for localhost)
        samesite="lax",  # not sent with cross-site POSTs (first line of CSRF defence)
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, httponly=True, secure=True, samesite="lax", path="/")


SessionToken = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


def get_current_user_optional(db: SessionDep, token: SessionToken = None) -> User | None:
    """The logged-in user, or None (for pages that work with and without login)."""
    return user_for_token(db, token) if token else None


CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]


def require_user(user: CurrentUserOptional) -> User:
    """For the JSON API: anonymous requests get 401, the client decides what to do."""
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return user


class LoginRequired(Exception):
    """Raised for anonymous HTML requests; main.py turns it into a redirect to the login page."""

    def __init__(self, next_url: str) -> None:
        self.next_url = next_url


def require_page_user(request: Request, user: CurrentUserOptional) -> User:
    """For HTML pages: anonymous visitors are sent to /ui/login and come back afterwards."""
    if user is None:
        # A dependency can't return a response, only raise. Remember path + query to return to.
        raise LoginRequired(
            request.url.path + (f"?{request.url.query}" if request.url.query else "")
        )
    return user


CurrentUser = Annotated[User, Depends(require_user)]
CurrentPageUser = Annotated[User, Depends(require_page_user)]


def is_safe_next(url: str | None) -> TypeGuard[str]:
    r"""Only allow redirects to a path on this site, never to another host ("open redirect").

    TypeGuard[str]: tells mypy that `url` is a str whenever this returns True.

    >>> [is_safe_next(u) for u in ["/ui/items/new?created=3", "/app/"]]
    [True, True]
    >>> [is_safe_next(u) for u in ["https://evil.example", "//evil.example", "/\\evil.example"]]
    [False, False, False]
    >>> [is_safe_next(u) for u in [None, "", "ui/items/new", "javascript:alert(1)"]]
    [False, False, False, False]
    """
    if not url or not url.startswith("/") or url.startswith("//") or "\\" in url:
        return False  # browsers treat "//host" and "/\\host" as "another host"
    parts = urlsplit(url)
    return not parts.scheme and not parts.netloc
