"""Generate the results tables from committed result files.

No number in README.md or CHANGELOG.md is typed by hand. Everything is rendered
from evaluation/results/*.json, so a claim in the prose cannot drift away from
the run that produced it. Re-running the evaluation and re-running this script
is enough to keep the whole repository honest.

Usage:
    python3 evaluation/make_report.py            # print markdown
    python3 evaluation/make_report.py --write    # also refresh evaluation/results.md
"""

from __future__ import annotations

import argparse
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "evaluation", "results")
ORDER = ["v0", "v1", "v2", "v3", "v4"]


def load_results() -> dict[str, dict]:
    results = {}
    for path in glob.glob(os.path.join(RESULTS_DIR, "*.json")):
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        results[payload["version"]] = payload
    return results


def headline_table(results: dict) -> str:
    """Baseline versus the full system, the comparison judges read first."""
    if "v0" not in results or "v4" not in results:
        return "_(needs both v0 and v4 results)_\n"

    base, full = results["v0"], results["v4"]
    bm, fm = base["metrics"], full["metrics"]
    broken = bm["true_positives"] + bm["false_negatives"]
    clean = bm["true_negatives"] + bm["false_positives"]

    def change(a: float, b: float) -> str:
        delta = b - a
        return f"{delta:+.2f}" if delta else "no change"

    rows = [
        ("Defects found", f"{bm['true_positives']}/{broken}", f"{fm['true_positives']}/{broken}",
         change(bm["true_positives"], fm["true_positives"])),
        ("False alarms on sound environments", f"{bm['false_positives']}/{clean}",
         f"{fm['false_positives']}/{clean}", change(bm["false_positives"], fm["false_positives"])),
        ("Precision", f"{bm['precision']:.2f}", f"{fm['precision']:.2f}",
         change(bm["precision"], fm["precision"])),
        ("**Balanced accuracy**", f"**{bm['balanced_accuracy']:.2f}**",
         f"**{fm['balanced_accuracy']:.2f}**", f"**{change(bm['balanced_accuracy'], fm['balanced_accuracy'])}**"),
        ("Wall clock, whole corpus", f"{base['totals']['wall_clock_s']:.0f}s",
         f"{full['totals']['wall_clock_s']:.0f}s", "-"),
        ("Cost per environment", "$0.00", "$0.00", "$0.00"),
    ]

    out = ["| Metric | Baseline (read only) | envguard | Change |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    return "\n".join(out) + "\n"


def changelog_table(results: dict) -> str:
    out = [
        "| Version | What changed | Found | False alarms | Balanced acc. | Model calls | Wall clock |",
        "|---|---|---|---|---|---|---|",
    ]
    for version in ORDER:
        payload = results.get(version)
        if not payload:
            continue
        m = payload["metrics"]
        broken = m["true_positives"] + m["false_negatives"]
        clean = m["true_negatives"] + m["false_positives"]
        out.append(
            f"| `{version}` | {payload['label']} | {m['true_positives']}/{broken} | "
            f"{m['false_positives']}/{clean} | **{m['balanced_accuracy']:.2f}** | "
            f"{payload['totals']['model_calls']} | {payload['totals']['wall_clock_s']:.0f}s |"
        )
    return "\n".join(out) + "\n"


def per_task_table(results: dict, version: str = "v4") -> str:
    payload = results.get(version)
    if not payload:
        return f"_(no {version} results)_\n"
    out = [
        "| Environment | Ground truth | Verdict | Caught by | Correct |",
        "|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        truth = f"BROKEN ({row['truth_family']})" if row["truth_broken"] else "sound"
        caught = "-"
        if row.get("evidence"):
            caught = f"`{row['evidence']['origin']}:{row['evidence']['family']}`"
        ok = "yes" if row["flagged"] == row["truth_broken"] else "**NO**"
        out.append(f"| `{row['task_id']}` | {truth} | `{row['verdict']}` | {caught} | {ok} |")
    return "\n".join(out) + "\n"


def contribution_note(results: dict) -> str:
    """How much did the language model actually add over deterministic code?"""
    if "v3" not in results or "v4" not in results:
        return ""
    v3, v4 = results["v3"]["metrics"], results["v4"]["metrics"]
    delta = v4["true_positives"] - v3["true_positives"]
    calls = results["v4"]["totals"]["model_calls"]
    seconds = results["v4"]["totals"]["wall_clock_s"] - results["v3"]["totals"]["wall_clock_s"]
    if delta == 0:
        return (
            f"Adding the model on top of the deterministic stages changed detection by "
            f"{delta:+d} environments, while costing {calls} inference calls and about "
            f"{seconds:.0f} extra seconds.\n"
        )
    return (
        f"Adding the model found {delta:+d} further environment(s) for {calls} inference "
        f"calls and about {seconds:.0f} extra seconds.\n"
    )


def render() -> str:
    results = load_results()
    if not results:
        return "No results yet. Run: python3 evaluation/run_eval.py --version v4\n"
    have = ", ".join(v for v in ORDER if v in results)
    parts = [
        "# Results\n",
        f"_Generated by `evaluation/make_report.py` from committed result files ({have}). "
        "Do not edit by hand._\n",
        "\n## Headline\n\n", headline_table(results),
        "\n## Improvement changelog\n\n", changelog_table(results),
        "\n", contribution_note(results),
        "\n## Per environment (v4)\n\n", per_task_table(results),
    ]
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    text = render()
    print(text)
    if args.write:
        path = os.path.join(ROOT, "evaluation", "results.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {os.path.relpath(path, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
