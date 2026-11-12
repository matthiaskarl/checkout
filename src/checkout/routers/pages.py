"""Server-rendered HTML pages (Jinja2), the small admin UI for items.

  /ui/                     -> redirect to the list
  /ui/items                list of all items, delete per row
  /ui/items/new            create form (GET shows it, POST saves)
  /ui/items/{id}/delete    POST only: deleting must never be a GET (links, prefetching)

Pattern: GET renders the form; POST validates and either re-renders the form with
errors (422) or saves and redirects (303, "Post/Redirect/Get") so a browser refresh
doesn't submit the form twice.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy import select

from checkout.auth import CurrentPageUser, require_csrf, require_page_user
from checkout.db import SessionDep
from checkout.models import Item, User
from checkout.schemas import ItemCreate
from checkout.templating import templates

# include_in_schema=False: HTML pages don't belong in the OpenAPI (JSON API) docs.
# Every page here requires a login (login/logout live in routers/login.py, which stays public).
# The routes also take `CurrentPageUser` to use the user; FastAPI runs the dependency only
# once per request and reuses the result, so this costs no second DB lookup.
router = APIRouter(
    prefix="/ui",
    include_in_schema=False,
    dependencies=[Depends(require_page_user), Depends(require_csrf)],
)


@router.get("/", name="ui_home")
def ui_home(request: Request) -> Response:
    return RedirectResponse(request.url_for("items_page"), status.HTTP_303_SEE_OTHER)


@router.get("/items", name="items_page")
def items_page(
    request: Request,
    session: SessionDep,
    current_user: CurrentPageUser,
    created: int | None = None,
    deleted: int | None = None,
) -> Response:
    """?created=<id> / ?deleted=<id>: one-off notices after a redirect (Post/Redirect/Get)."""
    items = session.scalars(select(Item).order_by(Item.id.desc())).all()
    context = {
        "items": items,
        "created": session.get(Item, created) if created is not None else None,
        "deleted": deleted,
        "current_user": current_user,
    }
    return templates.TemplateResponse(request, "items_list.html", context)


@router.post("/items/{item_id}/delete", name="delete_item_page")
def delete_item_page(
    request: Request,
    session: SessionDep,
    item_id: int,
    hx_request: Annotated[str | None, Header()] = None,
) -> Response:
    """One route for both kinds of caller, told apart by htmx's `HX-Request: true` header."""
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    session.delete(item)
    session.commit()

    if hx_request == "true":
        # htmx swaps this (empty) body in place of the row -> the row disappears.
        # 200, not 204: htmx deliberately does nothing on 204 No Content.
        return HTMLResponse("")
    url = request.url_for("items_page").include_query_params(deleted=item_id)
    return RedirectResponse(url, status.HTTP_303_SEE_OTHER)


def _render_new_item(
    request: Request,
    session: SessionDep,
    current_user: User,
    *,
    form: dict[str, str] | None = None,
    errors: dict[str, str] | None = None,
    status_code: int = status.HTTP_200_OK,
) -> Response:
    items = session.scalars(select(Item).order_by(Item.id.desc()).limit(10)).all()
    context: dict[str, Any] = {
        "form": form or {"name": "", "description": ""},
        "errors": errors or {},
        "items": items,
        "current_user": current_user,
    }
    return templates.TemplateResponse(request, "items_new.html", context, status_code=status_code)


@router.get("/items/new", name="new_item_page")
def new_item_page(
    request: Request,
    session: SessionDep,
    current_user: CurrentPageUser,
) -> Response:
    return _render_new_item(request, session, current_user)


@router.post("/items/new", name="create_item_page")
def create_item_page(
    request: Request,
    session: SessionDep,
    current_user: CurrentPageUser,
    name: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
) -> Response:
    form = {"name": name, "description": description}
    try:
        # Same Pydantic schema as the JSON API -> identical validation rules.
        data = ItemCreate(name=name.strip(), description=description.strip() or None)
    except ValidationError as exc:
        errors = {str(err["loc"][0]): err["msg"] for err in exc.errors()}
        return _render_new_item(
            request,
            session,
            current_user,
            form=form,
            errors=errors,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    item = Item(**data.model_dump())
    session.add(item)
    session.commit()

    url = request.url_for("items_page").include_query_params(created=item.id)
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)
