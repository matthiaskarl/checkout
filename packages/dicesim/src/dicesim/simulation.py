"""Monte Carlo simulation of a keep-and-reroll dice attempt.

Each die has a symbol printed on every face (default: 1,2,3 -> A; 4,5 -> B; 6 -> C).
An *attempt* consists of up to `rolls` rolls of `dice` dice: after each roll, dice
showing a symbol the goal still needs are kept, the rest are rerolled. The attempt
succeeds once every symbol of the goal (counted with multiplicity) has been kept.
"""

import math
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

#: Symbol on each face of a die, faces 1..6.
DEFAULT_FACES: tuple[str, ...] = ("A", "A", "A", "B", "B", "C")
DEFAULT_DICE = 5
DEFAULT_ROLLS = 3
DEFAULT_TRIALS = 10_000


@dataclass(frozen=True)
class SimulationResult:
    goal: tuple[str, ...]
    trials: int
    successes: int

    @property
    def probability(self) -> float:
        """Estimated probability that a single attempt reaches the goal."""
        return self.successes / self.trials

    @property
    def standard_error(self) -> float:
        """Standard error of the estimate; ±2 standard errors is roughly a 95% interval."""
        p = self.probability
        return math.sqrt(p * (1 - p) / self.trials)


def validate_inputs(goal: Sequence[str], *, faces: Sequence[str], dice: int, rolls: int) -> None:
    """Shared input checks for simulate() and exact_probability(). Raises ValueError."""
    if dice < 1 or rolls < 1:
        raise ValueError("dice and rolls must be at least 1")
    if not faces:
        raise ValueError("faces must not be empty")
    if not goal:
        raise ValueError("goal must contain at least one symbol")
    if len(goal) > dice:
        raise ValueError(f"goal has {len(goal)} symbols but there are only {dice} dice")
    unknown = sorted(set(goal) - set(faces))
    if unknown:
        raise ValueError(f"symbols not on any face: {', '.join(unknown)}")


def attempt(
    goal: Counter[str],
    rng: random.Random,
    *,
    faces: Sequence[str] = DEFAULT_FACES,
    dice: int = DEFAULT_DICE,
    rolls: int = DEFAULT_ROLLS,
) -> bool:
    """Play one attempt. Return True if all goal symbols were kept within `rolls` rolls."""
    needed = Counter(goal)
    remaining = sum(needed.values())
    free_dice = dice
    for _ in range(rolls):
        for symbol in (rng.choice(faces) for _ in range(free_dice)):
            if needed[symbol] > 0:  # keep the die
                needed[symbol] -= 1
                remaining -= 1
                free_dice -= 1
        if remaining == 0:
            return True
    return False


def simulate(
    goal: Sequence[str],
    *,
    trials: int = DEFAULT_TRIALS,
    faces: Sequence[str] = DEFAULT_FACES,
    dice: int = DEFAULT_DICE,
    rolls: int = DEFAULT_ROLLS,
    seed: int | None = None,
) -> SimulationResult:
    """Estimate the probability of reaching `goal` in one attempt, using `trials` attempts.

    >>> simulate(["A", "A", "A", "B", "C"]).probability  # doctest: +SKIP
    0.56  (varies by about ±0.01 between runs at 10,000 trials)

    Raises ValueError for an empty goal, a goal with more symbols than dice,
    symbols that appear on no face, or non-positive trials/dice/rolls.
    """
    if trials < 1:
        raise ValueError("trials must be at least 1")
    validate_inputs(goal, faces=faces, dice=dice, rolls=rolls)

    rng = random.Random(seed)
    goal_counts = Counter(goal)
    successes = sum(
        attempt(goal_counts, rng, faces=faces, dice=dice, rolls=rolls) for _ in range(trials)
    )
    return SimulationResult(goal=tuple(goal), trials=trials, successes=successes)
