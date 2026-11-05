"""Command line interface: `dicesim A A A B C [--exact] [--trials N] [--seed S] [--json]`."""

import argparse
import json
import sys
from collections.abc import Sequence

from dicesim.exact import exact_probability
from dicesim.simulation import (
    DEFAULT_DICE,
    DEFAULT_FACES,
    DEFAULT_ROLLS,
    DEFAULT_TRIALS,
    simulate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dicesim",
        description="Probability of rolling GOAL in one keep-and-reroll attempt "
        "(simulated by default, or calculated with --exact).",
    )
    parser.add_argument("goal", nargs="+", metavar="SYMBOL", help="goal symbols, e.g. A A A B C")
    parser.add_argument(
        "-n",
        "--trials",
        type=int,
        default=DEFAULT_TRIALS,
        help="attempts to simulate (default: %(default)s)",
    )
    parser.add_argument(
        "--rolls", type=int, default=DEFAULT_ROLLS, help="rolls per attempt (default: %(default)s)"
    )
    parser.add_argument(
        "--dice", type=int, default=DEFAULT_DICE, help="number of dice (default: %(default)s)"
    )
    parser.add_argument(
        "--faces",
        default=",".join(DEFAULT_FACES),
        help="comma-separated symbol for each face (default: %(default)s)",
    )
    parser.add_argument("--seed", type=int, help="random seed for reproducible results")
    parser.add_argument(
        "--exact",
        action="store_true",
        help="calculate the exact probability instead of simulating (ignores --trials/--seed)",
    )
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    faces = [f.strip() for f in args.faces.split(",") if f.strip()]
    label = f"P({' '.join(args.goal)} within {args.rolls} rolls)"
    if args.exact:
        try:
            probability = exact_probability(
                args.goal, faces=faces, dice=args.dice, rolls=args.rolls
            )
        except ValueError as exc:
            print(f"dicesim: error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps({"goal": args.goal, "method": "exact", "probability": probability}))
        else:
            print(f"{label} = {probability:.4f}  (exact)")
        return 0

    try:
        result = simulate(
            args.goal,
            trials=args.trials,
            faces=faces,
            dice=args.dice,
            rolls=args.rolls,
            seed=args.seed,
        )
    except ValueError as exc:
        print(f"dicesim: error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "goal": list(result.goal),
                    "method": "simulation",
                    "trials": result.trials,
                    "successes": result.successes,
                    "probability": result.probability,
                    "standard_error": result.standard_error,
                }
            )
        )
    else:
        print(
            f"{label} ≈ {result.probability:.4f}"
            f"  (± {2 * result.standard_error:.4f}, {result.successes}/{result.trials} attempts)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
