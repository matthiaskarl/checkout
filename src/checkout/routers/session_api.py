"""JSON login API for the React app: /api/session.

Same session logic as the Jinja2 login (checkout.sessions), different adapter:
JSON in/out instead of forms and redirects. The cookie is the same, so a login on
one frontend is a login on the other.

  GET    /api/session   who am I? -> username + CSRF token, or 401
  POST   /api/session   log in    -> sets the cookie, returns the same as GET
  DELETE /api/session   log out   -> 204 (needs X-CSRF-Token like every write)
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from checkout.auth import (
    LoginSessionOptional,
    SessionToken,
    clear_session_cookie,
    require_csrf,
    set_session_cookie,
)
from checkout.db import SessionDep
from checkout.models import LoginSession
from checkout.schemas import LoginRequest, SessionInfo
from checkout.sessions import authenticate, end_session, start_session

router = APIRouter(prefix="/session", tags=["session"])

LOGIN_FAILED = "Invalid username or password."


def _info(login: LoginSession) -> SessionInfo:
    return SessionInfo(username=login.user.username, csrf_token=login.csrf_token)


@router.get("", response_model=SessionInfo, responses={401: {"description": "Not logged in"}})
def get_session_info(login: LoginSessionOptional) -> SessionInfo:
    # Safe to return the CSRF token: other origins can't read this response (no CORS headers),
    # and same-origin pages can read the HTML forms anyway.
    if login is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return _info(login)


@router.post("", response_model=SessionInfo, responses={401: {"description": LOGIN_FAILED}})
def log_in(
    data: LoginRequest, db: SessionDep, response: Response, old_token: SessionToken = None
) -> SessionInfo:
    # No CSRF token possible yet; the app-wide Sec-Fetch-Site check covers login CSRF, and a
    # JSON body forces a CORS preflight for any other origin.
    user = authenticate(db, data.username, data.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, LOGIN_FAILED)
    token, login = start_session(db, user, replaces=old_token)
    set_session_cookie(response, token)  # FastAPI merges this into the JSON response
    return _info(login)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def log_out(db: SessionDep, response: Response, token: SessionToken = None) -> None:
    if token:
        end_session(db, token)
    clear_session_cookie(response)
