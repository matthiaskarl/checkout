"""Exact probability for the same keep-and-reroll rules as dicesim.simulation.

Idea: the only thing that matters during an attempt is *which goal symbols are still
missing* and *how many rolls are left* (the number of free dice follows from that).
So the probability can be defined recursively:

    P(missing, rolls_left) = sum over every way the free dice can fall:
                             P(that outcome) * P(missing after keeping, rolls_left - 1)

with P = 1 once nothing is missing and P = 0 when no rolls are left. Many paths lead
to the same (missing, rolls_left) situation, so results are cached: only a few dozen
distinct situations exist for 5 dice, which makes this take well under a millisecond.
"""

from collections import Counter
from collections.abc import Iterator, Sequence
from functools import cache
from math import factorial, prod

from dicesim.simulation import DEFAULT_DICE, DEFAULT_FACES, DEFAULT_ROLLS, validate_inputs


def exact_probability(
    goal: Sequence[str],
    *,
    faces: Sequence[str] = DEFAULT_FACES,
    dice: int = DEFAULT_DICE,
    rolls: int = DEFAULT_ROLLS,
) -> float:
    """Exact probability that a single attempt reaches `goal`.

    >>> round(exact_probability(["A", "A", "A", "B", "C"]), 4)
    0.5597

    Raises ValueError for the same invalid inputs as simulate().
    """
    validate_inputs(goal, faces=faces, dice=dice, rolls=rolls)

    # Probability of each symbol on a single die, e.g. {"A": 1/2, "B": 1/3, "C": 1/6}.
    face_counts = Counter(faces)
    symbols = sorted(face_counts)
    p = [face_counts[s] / len(faces) for s in symbols]

    def roll_outcomes(n: int) -> Iterator[tuple[tuple[int, ...], float]]:
        """Every way n dice can fall, as per-symbol counts, with its probability.

        E.g. (2, 1, 0) = "2 A, 1 B, 0 C" stands for all orderings of those dice;
        its probability is the multinomial n!/(k1! k2! k3!) * pA^k1 * pB^k2 * pC^k3.
        """

        def splits(i: int, left: int) -> Iterator[tuple[int, ...]]:
            if i == len(symbols) - 1:
                yield (left,)
                return
            for k in range(left + 1):
                for rest in splits(i + 1, left - k):
                    yield (k, *rest)

        for counts in splits(0, n):
            ways = factorial(n) // prod(factorial(k) for k in counts)
            yield counts, ways * prod(pi**k for pi, k in zip(p, counts, strict=True))

    @cache
    def success(needed: tuple[int, ...], rolls_left: int) -> float:
        """P(success) when `needed[i]` of symbol i are still missing."""
        missing = sum(needed)
        if missing == 0:
            return 1.0
        if rolls_left == 0:
            return 0.0
        free_dice = dice - (len(goal) - missing)  # dice not yet kept
        total = 0.0
        for counts, prob in roll_outcomes(free_dice):
            # Keep dice for still-needed symbols; extra copies are rerolled.
            still_needed = tuple(max(n - k, 0) for n, k in zip(needed, counts, strict=True))
            total += prob * success(still_needed, rolls_left - 1)
        return total

    goal_counts = Counter(goal)
    return success(tuple(goal_counts[s] for s in symbols), rolls)
