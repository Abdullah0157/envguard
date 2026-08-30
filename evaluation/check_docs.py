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

# Artifacts that make claims but are not prose, and were therefore outside the
# perimeter until a reviewer pointed out that two findings survived a revision
# specifically aimed at this class *because* they lived here. corpus/manifest.json
# asserted that t15 was "reachable only by the model" when no configuration
# reaches it, and evaluation/report.html led with a headline the README retracts.
# A claim is a claim whatever file it is in.
CLAIM_ARTIFACTS = (
    os.path.join("corpus", "manifest.json"),
    os.path.join("evaluation", "report.html"),
)

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

    # The refutation table has its own denominator: the number of broken
    # environments the baseline cleared, which is neither the broken count nor
    # the sound count. Derived from the generated file so it follows the corpus.
    _ref = os.path.join(ROOT, "evaluation", "refutations.md")
    if os.path.exists(_ref):
        with open(_ref, encoding="utf-8") as fh:
            _n = len([ln for ln in fh if ln.strip().startswith("| `t") and "passes" in ln])
        if _n:
            valid_denominators.add(_n)

    # The externally-authored held-out corpus has its own shape, and the README
    # quotes rates against it ("5/6 defects", "0/4 sound"). Derived from that
    # file rather than hardcoded, so if the reviewer's corpus is ever extended
    # the expectation follows it.
    heldout = os.path.join(ROOT, "evaluation", "heldout", "run_heldout.py")
    if os.path.exists(heldout):
        with open(heldout, encoding="utf-8") as fh:
            heldout_src = fh.read()
        h_broken = len(re.findall(r"\n\s*True,\s*\n?\s*[\"']", heldout_src))
        h_sound = len(re.findall(r"\n\s*False,\s*\n?\s*[\"']", heldout_src))
        if h_broken:
            valid_denominators |= {h_broken, h_sound, h_broken + h_sound}
    watch = {
        f"{n}/{d}"
        for d in range(1, 20) if d not in valid_denominators
        for n in range(0, d + 1)
    }

    for name in DOCS:
        text = read(name)
        # Three spellings of the same claim, because two reviewers independently
        # found that this check read only the slash form. "8 of 9" and "eight of
        # nine" sailed past a guard built to stop exactly that claim, and six
        # stale assertions were laundered through the gap. A guard with a blind
        # spot in a project whose thesis is "a claim that is not executed is not
        # evidence" is worse than no guard, because it certifies the thing it
        # cannot see.
        WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                 "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
                 "fifteen": 15}
        normalised = text
        # "eight of nine" -> "8/9"
        for word, digit in WORDS.items():
            normalised = re.sub(rf"\b{word}\b", str(digit), normalised, flags=re.I)
        # "8 of 9" -> "8/9"
        normalised = re.sub(r"(?<![\d/])(\d{1,3})\s+of\s+(\d{1,3})(?![\d/])",
                            r"\1/\2", normalised)

        hits = sorted({
            w for w in watch
            if re.search(rf"(?<![\d/]){re.escape(w)}(?![\d/])", text)
            or re.search(rf"(?<![\d/]){re.escape(w)}(?![\d/])", normalised)
        })
        # A doc may legitimately quote a historical figure, but only if it says so.
        # A document may quote a superseded rate while narrating the correction
        # that superseded it, but it has to say so. Two forms are accepted: the
        # marker on the same line, or a table whose heading paragraph declares the
        # whole block historical. The second exists because the corpus was
        # relabelled twice, and the measurements taken before each relabel are
        # still worth showing side by side; they simply cannot be renumbered,
        # because nobody re-ran those prompts against the corrected key.
        HIST = r"(earlier|stale|was false|relabel|at the time|historical|previous corpus|then stood|older corpus)"
        historical_blocks = []
        block: list[str] = []
        marked = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("|"):
                if marked:
                    block.append(line)
            else:
                if block:
                    historical_blocks.append("\n".join(block)); block = []
                # Blank lines do not clear the marker: a caption is normally
                # separated from its table by one.
                if stripped:
                    marked = bool(re.search(HIST, line, re.I))
        if block:
            historical_blocks.append("\n".join(block))
        historical_text = "\n".join(historical_blocks)

        hits = [
            h for h in hits
            if not re.search(rf"{re.escape(h)}[^\n]*{HIST}", text, re.I)
            and not re.search(rf"{HIST}[^\n]*{re.escape(h)}", text, re.I)
            and h not in historical_text
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

    # -------------------------------------------------- wall-clock operands
    # Every re-run rewrites wall_clock_s, so any second-value typed into prose
    # goes stale silently. This has happened twice: "883s" when v2 recorded
    # 857.2s, and later "857.2s versus 7.3s" after v2 and v3 were re-measured at
    # 790.0s and 6.8s. Both were caught by reviewers rather than by this file.
    #
    # A value is checked against the wall clock of the version NAMED ON THE SAME
    # LINE, not against the set of all of them. The first version of this check
    # matched against any committed run and passed a reintroduced "857.2s" for v2
    # (true value 790.0s) and a "72s" for v0 (true value 92.2s), because with
    # seven runs spanning 7s to 1064s almost any number is close to something.
    # That was found by reintroducing the defect, not by reading the code.
    SECONDS = re.compile(r"(?<![\w.])(\d{1,5}(?:\.\d)?)s(?![\w])")
    VERSION = re.compile(r"`?(v\d[\w-]*)`?")
    HISTORICAL = re.compile(
        r"(earlier|stale|was false|at the time|previously|used to|superseded|"
        r"recorded at the time|has since|transcription)", re.I
    )
    for name in DOCS:
        text = read(name)
        bad = []
        # Column headers carry the version for every row beneath them. Without
        # this, a row like "| Machine time | 72s | 391s | 7s |" names no version
        # and escapes the check entirely, which is how a stale 72s for v0 slipped
        # through the first version of it.
        #
        # A row counts as a header only when the NEXT line is the |---| separator.
        # Without that test a data row mentioning `v2` was mistaken for a header,
        # and the stale operand inside it was skipped. Found by reintroducing both
        # defects at once and watching only one of them get caught.
        lines = text.splitlines()
        separator = re.compile(r"^\s*\|[\s|:-]+\|\s*$")
        column_versions: list[list[str]] = []
        for number, line in enumerate(lines):
            stripped = line.strip()
            is_row = stripped.startswith("|") and stripped.endswith("|")
            if not is_row:
                column_versions = []
                continue
            if separator.match(line):
                continue

            cells = [c.strip() for c in stripped.strip("|").split("|")]
            is_header = number + 1 < len(lines) and separator.match(lines[number + 1])
            if is_header:
                column_versions = [
                    [v for v in VERSION.findall(c) if v in wall] for c in cells
                ]
                continue

            # A document may quote a superseded figure while narrating the bug it
            # caused, the same exemption the detection-rate check uses. It has to
            # say so on the line, which keeps the escape hatch narrow.
            if HISTORICAL.search(line):
                continue

            inline = [v for v in VERSION.findall(line) if v in wall]
            for index, cell in enumerate(cells):
                scope = inline or (
                    column_versions[index] if index < len(column_versions) else []
                )
                if not scope:
                    continue
                targets = [wall[v] for v in scope]
                for match in SECONDS.finditer(cell):
                    value = float(match.group(1))
                    # 8% covers rounding (6.8 written as 7, 790.0 as 790) and not
                    # the 67-second drift a stale operand produces.
                    if not any(abs(value - t) <= max(1.0, 0.08 * t) for t in targets):
                        bad.append((value, scope))

        # Prose outside tables, scoped to the LINE.
        #
        # Paragraph scoping was tried and reverted. It caught one more real case
        # but produced false positives: a paragraph naming v2 and v4 legitimately
        # quotes v3's 7s, and a note about 8B swap outliers mentions 200s next to
        # an unrelated v3 reference. A documentation gate that fails on correct
        # prose gets switched off, and then it protects nothing, so this one
        # prefers a known gap over a false alarm.
        #
        # KNOWN GAP, stated rather than hidden: a figure whose version is named on
        # a different line of the same sentence is not checked. The table pass
        # above covers the common case, since that is where operands actually live.
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") or HISTORICAL.search(line):
                continue
            inline = [v for v in VERSION.findall(line) if v in wall]
            if not inline:
                continue
            targets = [wall[v] for v in inline]
            for match in SECONDS.finditer(line):
                value = float(match.group(1))
                if not any(abs(value - t) <= max(1.0, 0.08 * t) for t in targets):
                    bad.append((value, inline))

        check(
            f"{name} quotes no wall clock that disagrees with the named version",
            not bad,
            f"found {bad}; committed wall clocks are "
            f"{ {v: round(w, 1) for v, w in sorted(wall.items())} }",
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

    # ---------------------------------------- claims living outside the prose
    # manifest.json: a note may not assert that a configuration reaches an
    # environment that every committed result reports as missed.
    manifest_raw = manifest
    all_results = load_all()
    overclaimed = []
    for task in manifest_raw["tasks"]:
        note = task.get("notes", "")
        if not re.search(r"reachable only by|only the model|only reachable", note, re.I):
            continue
        detected_by = [
            v for v, payload in all_results.items()
            if any(r["task_id"] == task["id"] and r["flagged"] for r in payload["rows"])
        ]
        if not detected_by:
            overclaimed.append(task["id"])
    check(
        "corpus/manifest.json claims no reachability the results contradict",
        not overclaimed,
        f"{overclaimed} are described as reachable by some configuration, but no "
        f"committed result flags them. A note in the answer key is a claim.",
    )

    # report.html: the human-facing artifact must carry the headline correction,
    # not the retracted comparison. It led with 0.61 against 0.94 for three
    # review rounds after the README had retracted exactly that framing.
    html_path = os.path.join(ROOT, "evaluation", "report.html")
    if os.path.exists(html_path):
        with open(html_path, encoding="utf-8") as fh:
            html = fh.read()
        best_readonly = max(
            (p for v, p in all_results.items() if v.startswith("v0")),
            key=lambda p: p["metrics"]["balanced_accuracy"],
        )
        needed = f"{best_readonly['metrics']['balanced_accuracy']:.2f}"
        check(
            "evaluation/report.html carries the headline correction",
            needed in html,
            f"report.html does not mention {needed}, the strongest read-only "
            f"result. The artifact a judge opens must not lead with a comparison "
            f"the README retracts. Rebuild with: ./run.sh report",
        )

    # ---------------------------------- the manifest's own prose and family keys
    # The answer key contradicted itself: manifest.json's description said
    # "9 carry a verifier defect; 6 are sound" while its per-task flags said 10
    # and 5, and defect_families defined D1..D9 while t13 was assigned D10.
    # This checker read the flags and never the prose in the same file, which is
    # the same blind spot as reading digits and not words: the guard covered the
    # machine-readable half of a file and certified the half a human reads.
    desc = manifest.get("description", "")
    desc_nums = re.findall(r"(\d+)\s+(?:carry|are|is)\b", desc)
    desc_problems = []
    if desc_nums:
        claimed = [int(n) for n in desc_nums[:2]]
        if claimed and claimed[0] != broken:
            desc_problems.append(f"description says {claimed[0]} broken, flags say {broken}")
        if len(claimed) > 1 and claimed[1] != sound:
            desc_problems.append(f"description says {claimed[1]} sound, flags say {sound}")
    check(
        "corpus/manifest.json description agrees with its own task flags",
        not desc_problems,
        "; ".join(desc_problems) + ". The answer key must not contradict itself.",
    )

    declared = set(manifest.get("defect_families", {}))
    used = {t["defect_family"] for t in manifest["tasks"] if t.get("defect_family")}
    undefined = sorted(used - declared)
    check(
        "every defect family a task uses is defined in the manifest",
        not undefined,
        f"{undefined} assigned to tasks but absent from defect_families. A family "
        f"key with no definition is a dangling reference in the answer key.",
    )

    # ------------------------------------- README's refutation table vs the generator
    # refutations.md is generated and always correct; the README copy is
    # transcribed and has now lost a row TWICE, both times while still asserting
    # a count. The first instance is documented in the README itself as a fixed
    # bug; relabelling t13 reintroduced it. Counting both sides ends the cycle.
    ref_md = os.path.join(ROOT, "evaluation", "refutations.md")
    if os.path.exists(ref_md):
        with open(ref_md, encoding="utf-8") as fh:
            generated = fh.read()
        gen_rows = [
            ln for ln in generated.splitlines()
            if ln.strip().startswith("| `t") and "passes" in ln
        ]
        readme = read("README.md")
        readme_rows = [
            ln for ln in readme.splitlines()
            if ln.strip().startswith("| `t") and "**passes**" in ln
        ]
        stated = re.search(r"\*\*(\d+) of (\d+)\*\* hold up", readme)
        problems = []
        if len(readme_rows) != len(gen_rows):
            problems.append(f"README shows {len(readme_rows)} rows, refutations.md has {len(gen_rows)}")
        if stated and int(stated.group(1)) != len(gen_rows):
            problems.append(f"README claims {stated.group(0)!r} against {len(gen_rows)} generated rows")
        check(
            "README's refutation table matches refutations.md",
            not problems,
            "; ".join(problems) + ". Regenerate with: python3 evaluation/refutations.py --write",
        )

    # --------------------------------------------- this script's own check count
    # The count is quoted in VERIFY.md and REPRODUCTION.md, and it has now gone
    # stale twice while this very file was growing (24 while it ran 27, then 27
    # while it ran 30). A stale number in the file whose purpose is preventing
    # stale numbers is the most embarrassing defect available here, so the count
    # checks itself. +1 accounts for this check, which has not run yet.
    total_checks = checks + 1
    stale_counts = []
    for name in DOCS:
        text = read(name)
        # Scoped to lines that are actually about this script. An unscoped version
        # matched "sandbox self-test: PASS (22 checks)" and demanded it equal the
        # documentation-check count, which is a different number for a different
        # thing.
        for line in text.splitlines():
            if not re.search(r"check_docs|documentation matches the evidence", line):
                continue
            for match in re.finditer(r"\((\d+) checks\)|(\d+) checks", line):
                stated = int(match.group(1) or match.group(2))
                if stated != total_checks:
                    stale_counts.append((name, stated))
    check(
        f"documents state the right number of checks ({total_checks})",
        not stale_counts,
        f"found {stale_counts}; this script runs {total_checks} checks",
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
