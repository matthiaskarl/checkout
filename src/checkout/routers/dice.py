"""JSON endpoint for the dicesim library.

The route is a thin adapter: it parses/validates the query, calls dicesim, and maps
dicesim's ValueError to a 422 response. All dice logic stays in the dicesim package.
"""

from enum import StrEnum
from typing import Annotated

import dicesim
from fastapi import APIRouter, Query
from fastapi.exceptions import RequestValidationError

from checkout.schemas import DicesimResult

router = APIRouter(prefix="/dicesim", tags=["dicesim"])

MAX_TRIALS = 100_000  # ~0.5 s per request; keeps a single request from hogging a worker


class Method(StrEnum):
    exact = "exact"
    simulation = "simulation"


@router.get("", response_model=DicesimResult, response_model_exclude_none=True)
def dicesim_probability(
    goal: Annotated[
        str,
        Query(
            description="Goal symbols, one character each, e.g. `AAABC`",
            min_length=1,
            max_length=dicesim.DEFAULT_DICE,
            examples=["AAABC"],
        ),
    ],
    method: Method = Method.exact,
    trials: Annotated[
        int, Query(ge=1, le=MAX_TRIALS, description="Attempts to simulate (simulation only)")
    ] = dicesim.DEFAULT_TRIALS,
    seed: Annotated[int | None, Query(description="Random seed (simulation only)")] = None,
) -> DicesimResult:
    """Probability of reaching `goal` with 5 keep-and-reroll dice in 3 rolls."""
    symbols = list(goal)
    try:
        if method is Method.exact:
            return DicesimResult(
                goal=symbols,
                method=method,
                probability=dicesim.exact_probability(symbols),
            )
        result = dicesim.simulate(symbols, trials=trials, seed=seed)
    except ValueError as exc:
        # Same error shape as FastAPI's own validation errors, pointing at the goal parameter.
        raise RequestValidationError(
            [{"type": "value_error", "loc": ("query", "goal"), "msg": str(exc), "input": goal}]
        ) from exc
    return DicesimResult(
        goal=symbols,
        method=method,
        probability=result.probability,
        trials=result.trials,
        successes=result.successes,
        standard_error=result.standard_error,
    )
