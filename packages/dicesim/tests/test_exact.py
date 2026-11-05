import json

import pytest
from dicesim import exact_probability, simulate
from dicesim.cli import main


def test_closed_form_cases() -> None:
    # One C: fail only if none of 15 dice-throws (5 dice x 3 rolls) shows C.
    assert exact_probability(["C"]) == pytest.approx(1 - (5 / 6) ** 15)
    # Five C: dice are independent, each needs a C within 3 rolls.
    assert exact_probability(["C"] * 5) == pytest.approx((1 - (5 / 6) ** 3) ** 5)
    # Single roll, single die, goal A: just P(A) = 3/6.
    assert exact_probability(["A"], dice=1, rolls=1) == pytest.approx(0.5)


def test_certain_goal() -> None:
    assert exact_probability(["A", "A"], faces=["A"]) == pytest.approx(1.0)


def test_known_values() -> None:
    assert exact_probability(list("BBBB")) == pytest.approx(0.5359, abs=1e-4)
    assert exact_probability(list("BBBC")) == pytest.approx(0.6013, abs=1e-4)
    assert exact_probability(list("AAABC")) == pytest.approx(0.5597, abs=1e-4)


@pytest.mark.parametrize("goal", ["AAABC", "BBBB", "BBBC", "BC", "CCC", "AABBC"])
def test_simulation_agrees_with_exact(goal: str) -> None:
    exact = exact_probability(list(goal))
    sim = simulate(list(goal), trials=20_000, seed=123)
    # 4 standard errors: a correct simulation fails this ~0.006% of the time; seeded -> stable.
    assert abs(sim.probability - exact) < 4 * sim.standard_error + 1e-9


def test_same_validation_as_simulate() -> None:
    for bad in ([], ["X"], ["A"] * 6):
        with pytest.raises(ValueError):
            exact_probability(bad)


def test_cli_exact(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["B", "B", "B", "C", "--exact"]) == 0
    assert capsys.readouterr().out.strip() == "P(B B B C within 3 rolls) = 0.6013  (exact)"

    assert main(["C", "--exact", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["method"] == "exact"
    assert data["probability"] == pytest.approx(1 - (5 / 6) ** 15)

    assert main(["Z", "--exact"]) == 2
