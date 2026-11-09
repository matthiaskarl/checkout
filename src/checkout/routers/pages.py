"""Server-rendered HTML pages (Jinja2).

Pattern: GET renders the form; POST validates and either re-renders the form with
errors (422) or saves and redirects back (303, "Post/Redirect/Get") so a browser
refresh doesn't submit the form twice.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, Response
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


def _render_new_item(
    request: Request,
    session: SessionDep,
    current_user: User,
    *,
    form: dict[str, str] | None = None,
    errors: dict[str, str] | None = None,
    created: Item | None = None,
    status_code: int = status.HTTP_200_OK,
) -> Response:
    items = session.scalars(select(Item).order_by(Item.id.desc()).limit(10)).all()
    context: dict[str, Any] = {
        "form": form or {"name": "", "description": ""},
        "errors": errors or {},
        "created": created,
        "items": items,
        "current_user": current_user,
    }
    return templates.TemplateResponse(request, "items_new.html", context, status_code=status_code)


@router.get("/items/new", name="new_item_page")
def new_item_page(
    request: Request,
    session: SessionDep,
    current_user: CurrentPageUser,
    created: int | None = None,
) -> Response:
    created_item = session.get(Item, created) if created is not None else None
    return _render_new_item(request, session, current_user, created=created_item)


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

    url = request.url_for("new_item_page").include_query_params(created=item.id)
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)
