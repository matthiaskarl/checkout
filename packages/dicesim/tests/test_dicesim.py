import json
import random
from collections import Counter

import pytest
from dicesim import attempt, simulate
from dicesim.cli import main


def test_reproducible_with_seed() -> None:
    a = simulate(["A", "A", "A", "B", "C"], trials=2_000, seed=7)
    b = simulate(["A", "A", "A", "B", "C"], trials=2_000, seed=7)
    assert a == b


def test_matches_exact_probability_for_single_symbol() -> None:
    # Goal "one C": fail only if no C shows in any of 3 rolls of 5 dice -> 15 dice, each 5/6 miss.
    exact = 1 - (5 / 6) ** 15
    result = simulate(["C"], trials=20_000, seed=1)
    assert abs(result.probability - exact) < 4 * result.standard_error + 1e-9


def test_certain_and_impossible_goals() -> None:
    assert simulate(["A"] * 5, faces=["A"], trials=100).probability == 1.0
    # More goal symbols than dice is rejected up front.
    with pytest.raises(ValueError, match="only 1 dice"):
        simulate(["C", "C"], dice=1)


def test_keeps_only_needed_dice() -> None:
    # All faces A: the first roll fills the goal, extra A's are irrelevant.
    rng = random.Random(0)
    assert attempt(Counter({"A": 2}), rng, faces=["A"], rolls=1)
    # Goal needs B but dice only show A -> never reached.
    assert not attempt(Counter({"B": 1}), rng, faces=["A", "A"], rolls=3)


@pytest.mark.parametrize(
    ("goal", "message"),
    [([], "at least one"), (["X"], "not on any face: X"), (["A"] * 6, "only 5 dice")],
)
def test_invalid_goals(goal: list[str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        simulate(goal)


def test_cli_text_and_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["A", "A", "A", "B", "C", "--trials", "500", "--seed", "3"]) == 0
    assert "P(A A A B C within 3 rolls)" in capsys.readouterr().out

    assert main(["C", "--trials", "500", "--seed", "3", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["trials"] == 500 and 0 <= data["probability"] <= 1


def test_cli_invalid_symbol(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["Z"]) == 2
    assert "not on any face: Z" in capsys.readouterr().err
