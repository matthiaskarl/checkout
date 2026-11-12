"""HTTP side of authentication: the session cookie and FastAPI dependencies."""

import secrets
from typing import Annotated, TypeGuard
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from checkout.apikeys import user_for_api_key
from checkout.db import SessionDep
from checkout.models import LoginSession, User
from checkout.sessions import SESSION_LIFETIME, valid_session

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


def get_login_session_optional(
    request: Request, db: SessionDep, token: SessionToken = None
) -> LoginSession | None:
    """The current login session, or None. Everything else below builds on this."""
    login = valid_session(db, token) if token else None
    request.state.login_session = login  # lets templates fill in csrf_token (templating.py)
    return login


LoginSessionOptional = Annotated[LoginSession | None, Depends(get_login_session_optional)]


def get_current_user_optional(login: LoginSessionOptional) -> User | None:
    """The logged-in user, or None (for pages that work with and without login)."""
    return login.user if login else None


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


# --- CSRF ---------------------------------------------------------------------------------

# Methods that must not change anything (we keep it that way), so they need no CSRF check.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CSRF_FIELD = "csrf_token"  # hidden form field (Jinja2 forms)
CSRF_HEADER = "X-CSRF-Token"  # request header (fetch from React, htmx)
FORM_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data")


def reject_cross_site_requests(request: Request) -> None:
    """Layer 1 (app-wide): refuse state-changing requests that the browser marks as foreign.

    Browsers add `Sec-Fetch-Site` to every request to HTTPS or localhost: "same-origin",
    "same-site" (other port/subdomain, e.g. the localhost:9000 demo), "cross-site" or
    "none" (typed URL, bookmark). Pages can't forge it. Clients like curl or scripts don't
    send it at all, so a missing header is allowed; the token check below covers those.
    """
    if request.method in SAFE_METHODS:
        return
    site = request.headers.get("sec-fetch-site")
    if site is not None and site not in ("same-origin", "none"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-origin request blocked")


# Reading the header via APIKeyHeader (instead of request.headers) documents it in OpenAPI:
# /api/docs gets an "Authorize" button where you paste the token from GET /api/session.
# auto_error=False: a missing header isn't an error here, we decide below.
csrf_header = APIKeyHeader(
    name=CSRF_HEADER,
    scheme_name="CSRF token",
    description="Value of csrf_token from GET /api/session (writes only).",
    auto_error=False,
)


async def require_csrf(
    request: Request,
    login: LoginSessionOptional,
    sent: Annotated[str | None, Depends(csrf_header)],
) -> None:
    """Layer 2 (per router): state-changing requests must echo the session's CSRF token.

    async because reading the form body is async. Starlette caches the parsed form, so the
    route's own Form(...) parameters still work afterwards.
    """
    if request.method in SAFE_METHODS or login is None:
        return  # no session cookie -> nothing to forge; require_user handles anonymous calls
    if sent is None and request.headers.get("content-type", "").startswith(FORM_TYPES):
        value = (await request.form()).get(CSRF_FIELD)
        sent = value if isinstance(value, str) else None
    # compare_digest takes the same time however many leading characters match.
    if not sent or not secrets.compare_digest(sent, login.csrf_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid")


# --- API keys (Authorization: Bearer) -----------------------------------------------------

# HTTPBearer parses "Authorization: Bearer <key>" and adds the "Authorize" field to
# /api/docs. auto_error=False: no header is fine here, the session is the fallback.
bearer = HTTPBearer(
    scheme_name="API key",
    description="An API key from `checkout-admin create-api-key` (starts with ck_).",
    auto_error=False,
)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]

# RFC 9110: a 401 must say which scheme would work. Scripts/tools read this header.
_BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def require_api_client(
    db: SessionDep, credentials: BearerCredentials, login: LoginSessionOptional
) -> User:
    """For the public API: a valid API key, or else a logged-in browser session.

    - Key sent: it must be valid. No fallback to the cookie, so a broken key shows up
      as an error instead of silently working in the browser and failing in the script.
    - No key: the session cookie (our own React/Jinja pages) works too. These routes are
      GET-only, so the cookie path needs no CSRF check; a key is never sent automatically
      by the browser, so the key path never needs one.
    """
    if credentials is not None:
        user = user_for_api_key(db, credentials.credentials)
        if user is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Invalid API key", headers=_BEARER_CHALLENGE
            )
        return user
    if login is not None:
        return login.user
    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED, "API key or login required", headers=_BEARER_CHALLENGE
    )
