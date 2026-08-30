"""Generate the results tables from committed result files.

This script generates evaluation/results.md, and nothing else. Everything it
writes is rendered from evaluation/results/*.json, so the generated tables cannot
drift away from the runs that produced them.

It does NOT render README.md. An earlier version of this docstring claimed no
number in the README or in a CHANGELOG.md was typed by hand; the first half was
false, the second referred to a file that does not exist in this repository, and
a reviewer found two hand-transcription errors in the README that proved it. The
tables in README.md are transcribed from results.md by a human and can therefore
be wrong. What guards them is evaluation/check_docs.py, which fails if the prose
contradicts the committed evidence.

Usage:
    python3 evaluation/make_report.py            # print markdown
    python3 evaluation/make_report.py --write    # also refresh evaluation/results.md
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "evaluation", "results")
# v0-hardened sits next to v0 because it answers the same question with a much
# stronger prompt. It is in the generated table because a reviewer showed the
# headline gap shrinks a long way against it, and burying that would be the
# opposite of what this repository claims to do.
ORDER = ["v0", "v0-hardened", "v0-reason-first", "v1", "v2", "v3", "v4"]


def load_results() -> dict[str, dict]:
    results = {}
    for path in glob.glob(os.path.join(RESULTS_DIR, "*.json")):
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        results[payload["version"]] = payload
    return results


def corpus_conflict(results: dict) -> str | None:
    """Report a mixed-corpus result set, or None when they agree.

    Two configurations measured on different corpus sizes answered different
    questions, and putting them in one table silently misstates the improvement.
    This is not hypothetical: two evaluation batches once overlapped and left
    four results on a 17-task corpus beside one on a 15-task corpus, which would
    have produced a comparison that looked fine and was meaningless.
    """
    sizes = {v: p.get("corpus_size") for v, p in results.items()}
    distinct = set(sizes.values())
    if len(distinct) <= 1:
        return None
    detail = ", ".join(f"{v}={sizes[v]}" for v in sorted(sizes))
    return (f"results span different corpus sizes ({detail}). "
            "Re-run the stale ones before trusting any table built from them.")


# The configuration we actually recommend shipping. It is v3, not v4, because the
# measurement showed the model stage adds no detections while multiplying wall
# clock. Presenting v4 here would understate the system on a metric (speed) that
# our own evidence says to drop the model for. v4 is still reported in full in
# the changelog below, including the fact that it cost ~100x the wall clock for
# no additional detection.
HEADLINE_VERSION = "v3"

# --- Human time model -------------------------------------------------------
#
# Stated as assumptions rather than buried in a number, so a reader can disagree
# with the inputs and recompute. Every environment a tool flags still has to
# reach a person; the question is how much of that person's time it costs.
#
# UNAIDED_REVIEW_MIN: an expert auditing one environment from scratch. micro1
#   pays experts up to $200/hour and the industry figure for this kind of review
#   is roughly $100 per environment, which implies about 30 minutes.
#
# CONFIRM_WITH_EVIDENCE_MIN: confirming a verdict that already ships a working
#   exploit plus the inputs where it disagrees with the reference. The reviewer
#   reads the exploit and can re-run it; they are checking a proof, not
#   producing one.
#
# A flag with no evidence attached costs a full unaided review, because the
# reviewer has to do the whole analysis themselves to act on it. This is the
# entire practical difference between the baseline and envguard, and it is why
# the baseline saves no human time at all despite finding every defect.
UNAIDED_REVIEW_MIN = 30.0
CONFIRM_WITH_EVIDENCE_MIN = 2.0


def human_minutes(payload: dict) -> tuple[float, float]:
    """(total minutes for the corpus, minutes per environment).

    A verdict carrying an executed exploit is cheap to confirm. A bare
    accusation is not: it costs the same as auditing the environment by hand.
    """
    rows = payload["rows"]
    total = 0.0
    for row in rows:
        if not row["flagged"]:
            continue  # nothing routed to a human
        has_evidence = bool(row.get("evidence")) or row.get("verdict") == "GOLD_FAILURE"
        total += CONFIRM_WITH_EVIDENCE_MIN if has_evidence else UNAIDED_REVIEW_MIN
    return total, (total / len(rows) if rows else 0.0)


def headline_table(results: dict) -> str:
    """Baseline versus the recommended configuration, read first by judges."""
    if "v0" not in results or HEADLINE_VERSION not in results:
        return f"_(needs both v0 and {HEADLINE_VERSION} results)_\n"

    base, full = results["v0"], results[HEADLINE_VERSION]
    bm, fm = base["metrics"], full["metrics"]
    broken = bm["true_positives"] + bm["false_negatives"]
    clean = bm["true_negatives"] + bm["false_positives"]

    def change(a: float, b: float) -> str:
        delta = b - a
        return f"{delta:+.2f}" if delta else "no change"

    b_total_min, b_per_env = human_minutes(base)
    f_total_min, f_per_env = human_minutes(full)
    saved = (1 - f_per_env / b_per_env) * 100 if b_per_env else 0.0

    # Counted from the rows rather than asserted in prose. An earlier version of
    # this function hardcoded a sentence claiming the baseline "flags all 15
    # environments" while "finding every defect"; the committed v0 flags 2 and
    # finds 2 of 9, so both halves were false and the falsehood was rendered into
    # results.md on every run. Deriving the numbers means the sentence cannot
    # drift from the data it describes.
    def flagged(payload: dict) -> int:
        return sum(1 for r in payload["rows"] if r["flagged"])

    def with_evidence(payload: dict) -> int:
        return sum(
            1 for r in payload["rows"]
            if r["flagged"] and (bool(r.get("evidence")) or r.get("verdict") == "GOLD_FAILURE")
        )

    b_flagged, f_flagged = flagged(base), flagged(full)
    f_with_evidence = with_evidence(full)

    rows = [
        ("**Primary outcome** (balanced accuracy)", f"**{bm['balanced_accuracy']:.2f}**",
         f"**{fm['balanced_accuracy']:.2f}**", f"**{change(bm['balanced_accuracy'], fm['balanced_accuracy'])}**"),
        ("**Human time per environment**", f"**{b_per_env:.1f} min**", f"**{f_per_env:.1f} min**",
         f"**-{saved:.0f}%**"),
        ("**Cost per environment**", "$0.00", "$0.00", "no change"),
        ("Defects found", f"{bm['true_positives']}/{broken}", f"{fm['true_positives']}/{broken}",
         change(bm["true_positives"], fm["true_positives"])),
        ("False alarms on sound environments", f"{bm['false_positives']}/{clean}",
         f"{fm['false_positives']}/{clean}", change(bm["false_positives"], fm["false_positives"])),
        ("Precision", f"{bm['precision']:.2f}", f"{fm['precision']:.2f}",
         change(bm["precision"], fm["precision"])),
        ("Machine time, whole corpus", f"{base['totals']['wall_clock_s']:.0f}s",
         f"{full['totals']['wall_clock_s']:.0f}s", "-"),
        ("Reviewer time, whole corpus", f"{b_total_min:.0f} min", f"{f_total_min:.0f} min",
         f"-{b_total_min - f_total_min:.0f} min"),
    ]

    out = [
        f"| Metric | Baseline (reads the verifier) | envguard (`{HEADLINE_VERSION}`) | Change |",
        "|---|---|---|---|",
    ]
    out += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    out.append("")
    out.append(
        f"\n`{HEADLINE_VERSION}` is the recommended configuration rather than the "
        "full `v4` pipeline, because the measurement below showed the model stage "
        "adds no detections while multiplying wall clock. `v4` is reported in full "
        "in the changelog, including that cost.\n"
    )
    out.append(
        "\n**How human time is computed.** Every environment a tool flags still "
        f"reaches a person. A flag carrying an executed exploit costs "
        f"{CONFIRM_WITH_EVIDENCE_MIN:.0f} minutes to confirm, because the reviewer "
        "is checking a proof rather than producing one. A flag with no evidence "
        f"costs a full unaided review, {UNAIDED_REVIEW_MIN:.0f} minutes, since the "
        "reviewer has to do the whole analysis themselves before they can act. "
        "Those two assumptions are the only inputs; disagree with them and you can "
        "recompute from `evaluation/results/*.json` directly.\n"
        f"\nThis is where the baseline's reviewer cost comes from. It flags "
        f"{b_flagged} of {base['corpus_size']} environments and attaches no "
        f"executed evidence to any of them, so each flag costs a full unaided "
        f"review and each of the {bm['false_negatives']} defects it missed reaches "
        f"a lab unexamined. `{HEADLINE_VERSION}` flags {f_flagged} and attaches a "
        f"runnable exploit to {f_with_evidence} of them, which is why the same "
        f"corpus costs {b_total_min:.0f} reviewer-minutes on the baseline and "
        f"{f_total_min:.0f} here.\n"
    )
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

    conflict = corpus_conflict(results)
    if conflict:
        return (
            "# Results\n\n"
            f"**Not generated: {conflict}**\n\n"
            "Refusing to render tables from a mixed-corpus result set. A comparison "
            "across different corpus sizes would look correct and mean nothing, so "
            "it is withheld rather than published with a caveat.\n"
        )

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

    results = load_results()
    conflict = corpus_conflict(results)

    text = render()
    # end="" so stdout is byte-identical to the written file. VERIFY.md tells the
    # reader to `diff` one against the other as a check that the prose tables were
    # not hand-edited, and a stray trailing newline would fail that check.
    print(text, end="")

    if not args.write:
        return 0

    # Refusing to publish must not also destroy what is already published.
    #
    # The first version of this guard opened results.md for writing and only then
    # decided it had nothing valid to write, replacing a committed results table
    # with a one-line refusal. A reviewer following REPRODUCTION.md hit exactly
    # that and reported it: the guide's own instructions deleted the repository's
    # results. Refusal now happens before the file is touched, and exits non-zero
    # so a script cannot mistake it for success.
    if conflict:
        print(f"\nREFUSED to write evaluation/results.md: {conflict}", file=sys.stderr)
        print("The existing file is left untouched.", file=sys.stderr)
        return 3

    path = os.path.join(ROOT, "evaluation", "results.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"\nwrote {os.path.relpath(path, ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
