# /// script
# requires-python = ">=3.12"
# ///
"""Read a `claude plugin eval --json` result and apply the gate from docs/skills.md.

The eval command already fails a case below the threshold. This adds the second half of
the gate: every case must score higher with the plugin than without it, or the skill is
not earning its place. Prints one line per case and exits 1 on any failure.

Usage: python scripts/eval_gate.py eval-result.json
"""

import json
import sys
from pathlib import Path


def failures(result: dict) -> list[str]:
    """Name every case that fails the gate. Pure: data in, data out."""
    problems = []
    for case in result.get("cases", []):
        aggregates = case.get("aggregates", {})
        score, delta = aggregates.get("score"), aggregates.get("delta")
        if score is None or score < 1.0:
            problems.append(f"{case['name']}: score {score} is below 1.0")
        if delta is None:
            problems.append(f"{case['name']}: no ablation delta; run with --ablation with-without")
        elif delta <= 0:
            problems.append(f"{case['name']}: delta {delta} means the skill changed nothing")
    if result.get("partial"):
        problems.append(f"partial run: {result.get('partialReason')}")
    return problems


_USAGE_ERROR = 2


def main(argv: list[str]) -> int:
    """Print each case's numbers, then the gate's verdict as the exit code."""
    match argv:
        case [_, result_path]:
            result = json.loads(Path(result_path).read_text(encoding="utf-8"))
        case _:
            print(__doc__, file=sys.stderr)
            return _USAGE_ERROR
    for case in result.get("cases", []):
        aggregates = case.get("aggregates", {})
        print(f"{case['name']}: score {aggregates.get('score')} delta {aggregates.get('delta')}")
    problems = failures(result)
    for problem in problems:
        print(f"gate: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
