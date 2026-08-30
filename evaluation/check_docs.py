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

import ast
import glob
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


def load_all() -> dict:
    """Every committed result file, keyed by version. Discovered, not listed."""
    found = {}
    for path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        found[payload["version"]] = payload
    return found


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

    # The shapes the documents must never contain: a confusion-matrix denominator
    # that is neither the broken count nor the sound count.
    #
    # Keyed on the DENOMINATOR only. An earlier version watched for {tp}/d and
    # {fp}/d separately, which flagged "0/9" in a table reporting that a hardened
    # baseline attempt found 0 of the 9 defects. That is a perfectly valid
    # detection rate; the check had assumed any "0/d" must be a false-alarm rate.
    # A denominator of 9 or 6 is always legitimate whatever sits above it.
    # broken, sound, and the corpus size are all legitimate denominators:
    # "8/9" defects, "0/6" false alarms, "15/15" environments audited.
    valid_denominators = {broken, sound, total}
    watch = {
        f"{n}/{d}"
        for d in range(1, 20) if d not in valid_denominators
        for n in range(0, d + 1)
    }

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
    # Discovered, not hardcoded. A hardcoded ("v0","v1",...) list failed the
    # moment v0-hardened was added: the README correctly reported its 0.67 and
    # the checker called it unsupported, because the checker did not know the
    # result file existed. Enumerating the directory means a new configuration
    # is covered the moment it is committed.
    committed_ba = {
        f"{payload['metrics']['balanced_accuracy']:.2f}"
        for payload in (load_all().values())
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
    models_used = {payload["model"] for payload in load_all().values()}
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

    # ------------------------------------------- the retracted provenance claim
    # The README once claimed every number in it was machine-rendered. That was
    # false, and retracting it in one file while three others kept asserting it is
    # the exact defect this script exists to prevent. So the retraction is an
    # invariant: the claim may appear only where it is being withdrawn.
    RETRACTED = re.compile(
        r"(no (?:number|figure)[^.\n]{0,60}typed by hand"
        r"|not? typed by hand"
        r"|every number[^.\n]{0,40}(?:is )?(?:rendered|generated)[^.\n]{0,30}by)",
        re.I,
    )
    WITHDRAWN_NEARBY = re.compile(
        r"(retract|withdraw|was false|earlier version|no longer|does not exist|overclaim)",
        re.I,
    )
    for name in (*DOCS, os.path.join("evaluation", "make_report.py")):
        text = read(name)
        offenders = []
        for m in RETRACTED.finditer(text):
            # Look at the surrounding paragraph, not just the line: the retraction
            # is usually stated in the sentence before or after the quote.
            lo, hi = max(0, m.start() - 400), min(len(text), m.end() + 400)
            if not WITHDRAWN_NEARBY.search(text[lo:hi]):
                offenders.append(text[m.start():m.end()][:70])
        check(
            f"{name} does not assert the retracted 'nothing typed by hand' claim",
            not offenders,
            f"found {offenders}. That mechanism does not exist: make_report.py "
            f"generates results.md only, and the README tables are transcribed by "
            f"hand. State it only where it is being withdrawn.",
        )

    # -------------------------------------------------------- multiplier claims
    # "N times slower" is a derived figure like any other, so it is checked like
    # any other. A reviewer found 126x, ~120x and 117x coexisting in one README.
    wall = {v: p["totals"]["wall_clock_s"] for v, p in load_all().items()}
    ratios = {
        round(wall[a] / wall[b])
        for a in wall for b in wall
        if a != b and wall[b] and wall[a] > wall[b]
    }
    MULT = re.compile(r"(\d{2,4})\s*(?:x|times)\s+(?:the\s+)?(?:wall clock|slower|slow)", re.I)
    for name in (*DOCS, os.path.join("evaluation", "make_report.py")):
        text = read(name)
        claimed = {int(m.group(1)) for m in MULT.finditer(text)}
        # Must round to a real pairwise ratio between committed wall clocks.
        # The tolerance is deliberately tight (2%, floor of 1). A looser 5% band
        # was tried first and let "94x" pass against a true 97x, which is exactly
        # the kind of near-miss that produced this check in the first place.
        # Tolerance is 15%, not 2%, and the reason is a defect this check found in
        # itself. Wall clock is machine-dependent and varies between runs: v3 has
        # been recorded at both 7.3s and 6.8s, which moves the v2/v3 ratio from
        # 117 to 126 without anything about the system changing. A tight band made
        # correct prose fail whenever a result file was refreshed, so it was
        # enforcing precision the measurement cannot support. Documents should
        # quote one approximate multiplier; this checks they agree with the
        # evidence and with each other, not that they track timing noise.
        bad = [c for c in claimed if not any(abs(c - r) <= max(1, 0.15 * r) for r in ratios)]
        check(
            f"{name} quotes no multiplier absent from the committed wall clocks",
            not bad,
            f"found {sorted(bad)}x; committed wall clocks are {wall}, giving "
            f"ratios {sorted(ratios)}",
        )

    # ------------------------------------------------- corpus contamination
    # A reviewer found that t08_days_between's verifier carried a comment stating
    # its own defect in plain English. It was the only commented verifier in
    # fifteen, and it was the exact environment the README claimed no read-only
    # baseline could ever flag. With the comment a read-only baseline flags it
    # every time; without it, never. The structural claim was right on the merits
    # and false as the corpus shipped.
    #
    # A verifier is an artefact under audit, not documentation. Prose inside one
    # leaks the answer to any reader, so none of them get prose.
    commented = []
    for path in sorted(glob.glob(os.path.join(ROOT, "corpus", "tasks", "*", "verifier.py"))):
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        try:
            tree = ast.parse(body)
        except SyntaxError:
            continue
        has_docstring = bool(ast.get_docstring(tree))
        has_comment = any(
            line.strip().startswith("#") for line in body.splitlines()
        )
        if has_comment or has_docstring:
            commented.append(os.path.basename(os.path.dirname(path)))
    check(
        "no verifier explains itself in prose",
        not commented,
        f"{commented} contain comments or docstrings. A verifier is the artefact "
        f"under audit; prose inside one hands the answer to a read-only reader "
        f"and contaminates every baseline measurement.",
    )

    # ---------------------------------------------- the hardened baseline exists
    # The headline comparison must not rest on a weak baseline alone. A reviewer
    # showed most of the original 0.61-to-0.94 gap was a property of the v0
    # prompt, so a stronger read-only baseline is now committed and reported.
    hardened_path = os.path.join(RESULTS, "v0-hardened.json")
    check(
        "a hardened read-only baseline is committed",
        os.path.exists(hardened_path),
        "evaluation/results/v0-hardened.json is missing. Without it the headline "
        "compares envguard only against the weakest prompt, which a reviewer "
        "already demonstrated overstates the improvement.",
    )
    if os.path.exists(hardened_path):
        readme = read("README.md")
        hardened_ba = f"{load('v0-hardened')['metrics']['balanced_accuracy']:.2f}"
        check(
            "README reports the hardened baseline's balanced accuracy",
            hardened_ba in readme,
            f"the committed hardened baseline scores {hardened_ba} and the README "
            f"does not state it, so the honest comparison is not on the page",
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
