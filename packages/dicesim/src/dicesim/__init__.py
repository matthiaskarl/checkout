"""dicesim: the chance of rolling a symbol goal with keep-and-reroll dice.

Two ways to get the probability for the same rules:

>>> from dicesim import exact_probability, simulate
>>> round(exact_probability(["A", "A", "A", "B", "C"]), 4)  # exact
0.5597
>>> result = simulate(["A", "A", "A", "B", "C"], trials=10_000)  # Monte Carlo estimate
>>> abs(result.probability - 0.5597) < 0.03
True
"""

from dicesim.exact import exact_probability
from dicesim.simulation import (
    DEFAULT_DICE,
    DEFAULT_FACES,
    DEFAULT_ROLLS,
    DEFAULT_TRIALS,
    SimulationResult,
    attempt,
    simulate,
)

__all__ = [
    "DEFAULT_DICE",
    "DEFAULT_FACES",
    "DEFAULT_ROLLS",
    "DEFAULT_TRIALS",
    "SimulationResult",
    "attempt",
    "exact_probability",
    "simulate",
]
