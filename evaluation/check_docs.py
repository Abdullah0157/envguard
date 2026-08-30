"""Fail if the documentation contradicts the committed evidence.

Why this file exists
--------------------
An external reviewer ran the sixty-second check this repository tells judges to
run, and got numbers different from the ones the documentation told them to
expect. The cause was not a bad measurement. It was that `t15_safe_divide` was
relabelled from sound to broken late in the build, which moved the corpus from
"8 broken, 7 sound" to "9 broken, 6 sound", and three documents were never
updated: README.md, REPRODUCTION.md, and VERIFY.md, the last of which is the
document written specifically for a reviewer.

That is the worst kind of defect in a project whose entire argument is "do not
trust assertions, execute something". The numbers were right and the prose was
wrong, so a reader checking the work found a mismatch and had every reason to
stop trusting the rest.

Fixing the stale text was necessary but not sufficient, because nothing stopped
it happening again the next time a label changed. This script is the stop. It
derives the true figures from the committed result files and the manifest, then
refuses to pass if any document states something else.

Run it:

    python3 evaluation/check_docs.py

Exit codes: 0 all consistent, 1 a document contradicts the evidence.
"""

from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "evaluation", "results")

DOCS = ("README.md", "REPRODUCTION.md", "VERIFY.md")

failures: list[str] = []
checks = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if ok:
        print(f"  [ok] {label}")
    else:
        print(f"  [FAIL] {label}" + (f"\n         {detail}" if detail else ""))
        failures.append(label)


def read(name: str) -> str:
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


def load(version: str) -> dict:
    with open(os.path.join(RESULTS, f"{version}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    print("=" * 78)
    print("documentation vs committed evidence")
    print("=" * 78)

    # ---------------------------------------------------------------- corpus
    with open(os.path.join(ROOT, "corpus", "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    broken = sum(1 for t in manifest["tasks"] if t["broken"])
    sound = sum(1 for t in manifest["tasks"] if not t["broken"])
    total = broken + sound
    print(f"\ncorpus: {total} environments, {broken} broken, {sound} sound\n")

    v0, v3 = load("v0"), load("v3")
    tp, fp = v3["metrics"]["true_positives"], v3["metrics"]["false_positives"]
    ba = v3["metrics"]["balanced_accuracy"]

    # The shapes the documents must never contain: any confusion-matrix
    # denominator that disagrees with the corpus as it actually stands.
    stale_detected = [
        f"{n}/{d}" for d in range(1, 20) if d != broken for n in range(0, d + 1)
    ]
    # Only the ones that would plausibly be written as a detection rate.
    watch = {f"{tp}/{d}" for d in range(1, 20) if d != broken}
    watch |= {f"{fp}/{d}" for d in range(1, 20) if d != sound}
    del stale_detected

    for name in DOCS:
        text = read(name)
        hits = sorted({w for w in watch if re.search(rf"(?<![\d/]){re.escape(w)}(?![\d/])", text)})
        # A doc may legitimately quote a historical figure, but only if it says so.
        hits = [
            h for h in hits
            if not re.search(rf"{re.escape(h)}[^\n]*(earlier|stale|was false|relabel|at the time|historical)", text)
            and not re.search(rf"(earlier|stale|was false|relabel|at the time|historical)[^\n]*{re.escape(h)}", text)
        ]
        check(
            f"{name} states no stale detection rate",
            not hits,
            f"found {hits}; the corpus is {broken} broken / {sound} sound, so the "
            f"only correct shapes are N/{broken} and N/{sound}",
        )

    # ------------------------------------------------------- headline figures
    # Every balanced accuracy quoted in prose must be one a committed result
    # file actually contains. 0.50 is additionally allowed because it is the
    # arithmetic score of the always-say-hackable stub, not a measurement.
    committed_ba = {
        f"{load(v)['metrics']['balanced_accuracy']:.2f}" for v in ("v0", "v1", "v2", "v3", "v4")
    }
    allowed_ba = committed_ba | {"0.50"}
    for name in DOCS:
        text = read(name)
        quoted = set(re.findall(r"balanced accuracy[^\n\d]{0,12}(\d\.\d\d)", text, re.I))
        quoted |= set(re.findall(r"BALANCED ACC\s+(\d\.\d\d)", text))
        bad = {q for q in quoted if q not in allowed_ba}
        check(
            f"{name} quotes no balanced accuracy absent from the results",
            not bad,
            f"found {sorted(bad)}; committed values are {sorted(committed_ba)} "
            f"(plus 0.50 for the trivial stub)",
        )

    # ------------------------------------------------------------ model default
    llm = read(os.path.join("envguard", "llm.py"))
    m = re.search(r'DEFAULT_MODEL\s*=\s*os\.environ\.get\(\s*"ENVGUARD_MODEL"\s*,\s*"([^"]+)"', llm)
    default_model = m.group(1) if m else "?"
    models_used = {load(v)["model"] for v in ("v0", "v1", "v2", "v3", "v4")}
    check(
        "envguard/llm.py default model is the one the results were measured with",
        default_model in models_used,
        f"default is {default_model!r} but committed results used {sorted(models_used)}. "
        f"Four changelog rows would not reproduce with documented defaults.",
    )

    run_sh = read("run.sh")
    m = re.search(r'MODEL="\$\{ENVGUARD_MODEL:-([^}]+)\}"', run_sh)
    check(
        "run.sh default model matches envguard/llm.py",
        m is not None and m.group(1) == default_model,
        f"run.sh has {m.group(1) if m else '?'!r}, llm.py has {default_model!r}",
    )

    # -------------------------------------------------------- trajectory drift
    traj_path = os.path.join(ROOT, "trajectories", "05-baseline-judge.md")
    if os.path.exists(traj_path):
        with open(traj_path, encoding="utf-8") as fh:
            traj = fh.read()
        m = re.search(r"\*\*Verdict:\*\*\s*`(\w+)`", traj)
        shown = m.group(1) if m else "?"
        row = next(r for r in v0["rows"] if r["task_id"] == "t03_slugify")
        expected = row["verdict"]
        check(
            "trajectories/05-baseline-judge.md agrees with v0.json on t03_slugify",
            shown == expected,
            f"trajectory shows {shown!r}, evaluation/results/v0.json records "
            f"{expected!r}. The trajectory argues about a verdict the evidence "
            f"does not contain.",
        )

    # ------------------------------------------------- the work product is linked
    readme = read("README.md")
    check(
        "README.md points at evaluation/report.html",
        "report.html" in readme,
        "the human-facing audit report is the best artifact here and nothing links it",
    )
    check(
        "run.sh exposes a report target",
        "cmd_report" in run_sh and "report)" in run_sh,
        "add ./run.sh report so the HTML report is reachable without reading source",
    )

    # ------------------------------------------------- every claim has evidence
    for version in ("v0", "v1", "v2", "v3", "v4"):
        path = os.path.join(RESULTS, f"{version}.json")
        check(
            f"{version} referenced in the changelog has a committed result file",
            os.path.exists(path),
            f"{path} is missing, so that changelog row rests on nothing",
        )

    print()
    print("=" * 78)
    if failures:
        print(f"RESULT: FAIL - {len(failures)} of {checks} checks failed")
        for f in failures:
            print(f"  - {f}")
        print("=" * 78)
        return 1
    print(f"RESULT: PASS - documentation matches the evidence ({checks} checks)")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
