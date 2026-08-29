"""Validate the corpus against its own answer key.

This must pass before any result in this repository means anything. It proves
four properties by execution rather than assertion:

  1. Every gold solution passes its verifier, except the D8 task, whose whole
     defect is that the correct answer fails.
  2. Every broken task (other than D8) really is beatable, so "broken" is a fact
     rather than a label we typed into a JSON file.
  3. No clean task is beatable by any deterministic template. If this fails, the
     task is not clean and the answer key is wrong.
  4. No template exploit is a universal harness bypass, so per-task detections
     are genuinely per-task.

Run:  python3 evaluation/check_corpus.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "envguard"))

from attacks import build_attacks  # noqa: E402
from corpus import load_tasks  # noqa: E402
from sandbox import is_harness_bypass, run_candidate  # noqa: E402

GREEN = "ok"
RED = "FAIL"


def main() -> int:
    tasks = load_tasks()
    failures = 0
    rows = []

    print("=" * 78)
    print("CORPUS ANSWER-KEY VALIDATION")
    print("=" * 78)

    for task in tasks:
        # --- property 1: does the gold solution pass its own verifier? ---
        gold = run_candidate(task.verifier_src, task.solution_src)
        gold_should_pass = task.defect_family != "D8"
        gold_ok = gold.passed == gold_should_pass
        failures += 0 if gold_ok else 1

        # --- properties 2 and 3: which templates get through? ---
        attacks = build_attacks(
            task.solution_src, task.verifier_src, task.entrypoints, task.entrypoint
        )
        winners = []
        for attack in attacks:
            result = run_candidate(task.verifier_src, attack.source)
            if result.passed:
                winners.append(attack.family)

        if not task.broken:
            # A sound environment must survive every deterministic attack, or the
            # "clean" label is wrong and every false-alarm number is meaningless.
            expectation_ok = len(winners) == 0
            note = "resisted every template" if expectation_ok else f"LEAKED via {winners}"
        elif task.template_beatable:
            expectation_ok = len(winners) > 0
            note = "beatable as designed" if expectation_ok else "NOT BEATABLE - mislabelled"
        elif task.defect_family == "D8":
            # Broken at the root: the reference solution fails its own verifier, so
            # there is nothing to exploit and only the sanity gate can reach it.
            expectation_ok = len(winners) == 0 and not gold.passed
            note = "gold fails, unreachable by attack (sanity-gate only)" if expectation_ok else "D8 assumptions violated"
        else:
            # D9: genuinely broken, gold passes, but the exploit is a mapping over
            # the tested inputs. No single-constant template can express that, so
            # templates MUST fail here. If one succeeds, the task is not measuring
            # what it claims and the "templates cannot reach this" story collapses.
            expectation_ok = len(winners) == 0 and gold.passed
            note = ("gold passes, no template can express the exploit (model-only)"
                    if expectation_ok else "D9 assumptions violated")
        failures += 0 if expectation_ok else 1

        rows.append(
            (task.id, task.defect_family or "-", gold.summary(), len(winners), winners[:3], note, gold_ok and expectation_ok)
        )

    for task_id, family, gold_summary, count, sample, note, ok in rows:
        mark = GREEN if ok else RED
        sample_text = ", ".join(sample) + ("..." if count > 3 else "")
        print(f"  [{mark:4s}] {task_id:26s} {family:3s} gold={gold_summary:22s} beaten_by={count:2d} {sample_text}")
        if not ok:
            print(f"           -> {note}")

    # --- property 4: no template may be a universal harness bypass ---
    print("-" * 78)
    bypass_hits = []
    checked = set()
    for task in tasks:
        for attack in build_attacks(
            task.solution_src, task.verifier_src, task.entrypoints, task.entrypoint
        ):
            key = (task.id, attack.family)
            if key in checked:
                continue
            checked.add(key)
            if is_harness_bypass(attack.source):
                bypass_hits.append(key)
    if bypass_hits:
        failures += 1
        print(f"  [{RED}] {len(bypass_hits)} template(s) are universal harness bypasses: {bypass_hits[:5]}")
    else:
        print(f"  [{GREEN}] no template is a universal harness bypass ({len(checked)} checked)")

    broken = [t for t in tasks if t.broken]
    clean = [t for t in tasks if not t.broken]
    print("-" * 78)
    print(f"  corpus: {len(tasks)} tasks, {len(broken)} broken, {len(clean)} clean")
    print("=" * 78)
    print("RESULT:", "PASS - answer key is sound" if failures == 0 else f"{failures} PROBLEM(S) - answer key is NOT sound")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
