"""The dice section of the Jinja2 UI (htmx partial reload).

  GET /ui/dice?symbol=A&symbol=A&symbol=B&symbol=&symbol=
      -> only the HTML fragment with the result (templates/_dice_result.html)

htmx swaps that fragment into the page, so only the result area changes. Unlike the
React app, which calls the JSON API (/api/dicesim), this calls the dicesim library
directly in Python: htmx wants HTML back, not JSON.
"""

from typing import Annotated, Any

import dicesim
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from checkout.auth import require_page_user
from checkout.templating import templates

router = APIRouter(prefix="/ui", include_in_schema=False, dependencies=[Depends(require_page_user)])

# Derived from the library, so the selects follow if the dice ever change.
FACES = sorted(set(dicesim.DEFAULT_FACES))  # ["A", "B", "C"]
DICE = dicesim.DEFAULT_DICE  # 5 selects

SymbolParams = Annotated[list[str] | None, Query(alias="symbol")]


def dice_context(symbols: list[str] | None) -> dict[str, Any]:
    """Everything _dice.html / _dice_result.html need. symbols=None: nothing chosen yet."""
    chosen = (symbols or [])[:DICE]
    context: dict[str, Any] = {
        "faces": FACES,
        "selected": chosen + [""] * (DICE - len(chosen)),  # one value per select, "" = none
        "submitted": symbols is not None,
        "goal": None,
        "probability": None,
        "error": None,
    }
    if symbols is None:
        return context

    goal = sorted(s for s in chosen if s)  # order doesn't matter for the probability
    if not goal:
        context["error"] = "Choose at least one symbol."
        return context
    try:
        context["probability"] = dicesim.exact_probability(goal)
        context["goal"] = " ".join(goal)
    except ValueError as exc:  # e.g. a hand-made URL with an unknown symbol
        context["error"] = str(exc)
    return context


@router.get("/dice", name="dice_result")
def dice_result(request: Request, symbols: SymbolParams = None) -> Response:
    # A safe GET (computes, changes nothing), so no CSRF token involved.
    context = {"dice": dice_context(symbols or [])}
    return templates.TemplateResponse(request, "_dice_result.html", context)
