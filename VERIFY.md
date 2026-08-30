# Verify this yourself

Every claim this project makes is checkable by running a command. This document
pairs each claim with the command that would **disprove** it if it were false.

You are not asked to trust the README. You are asked to try to break it.

---

## 1. The sixty second check

If you only run one thing:

```bash
python3 evaluation/run_eval.py --version v3
```

Expected last lines:

```
detected        8/9 broken environments
false alarms    0/6 clean environments
recall          0.89
specificity     1.00
precision       1.00
BALANCED ACC    0.94   (always-say-hackable scores 0.50)
wall clock      ~7s for 15 environments
model calls     0
cost            $0.00 (local inference)
misses:
  - t15_safe_divide            MISSED DEFECT: Survived 14 executed attack(s).
```

If that prints 8/9 and 0/6, the central claim holds: the system finds eight of
the nine planted defects and falsely accuses nothing, without calling a language
model.

**The reported miss is deliberate.** `t15_safe_divide` was found to be broken by
an external adversarial reviewer, in an environment this project had labelled
sound. It was relabelled rather than deleted, and no attack was written for it,
because fitting an attack to a known answer measures nothing. If your run prints
`8/9` with `t15_safe_divide` in the misses list, that is the expected result and
not a degraded one. See the "known miss" section of the README.

---

## 2. Claim by claim

| # | Claim in README | Command that checks it | What proves it false |
|---|---|---|---|
| 1 | The sandbox really isolates and really detects | `python3 envguard/sandbox.py` | Anything other than `sandbox self-test: PASS`. 22 checks including timeouts, print bombs, orphaned processes, and forged success tokens. |
| 2 | The answer key is correct, not just asserted | `python3 evaluation/check_corpus.py` | Anything other than `RESULT: PASS`. It executes every task to prove broken ones are beatable and sound ones are not. |
| 3 | The baseline finds 2 of 9 and scores 0.61, barely above the 0.50 an always-say-yes stub gets | `python3 evaluation/run_eval.py --version v0` | A balanced accuracy meaningfully above 0.61, or more than 2 defects found. |
| 4 | envguard scores 0.94 with zero model calls, missing only `t15_safe_divide` | `python3 evaluation/run_eval.py --version v3` | Fewer than 8/9 found, any false alarm, a nonzero model call count, or a *different* task in the misses list. |
| 5 | Adding the model *on top of* templates yields +0 detections | `python3 evaluation/run_eval.py --version v4`, compare to v3 | v4 finding a defect that v3 missed. |
| 5b | The model is redundant, **not** incapable: it finds 8/9 unaided, just 117x slower | `python3 evaluation/run_eval.py --version v2`, compare to v3 | v2 scoring below 8/9, which would mean the README oversells the model rather than the templates. |
| 6 | All 6 checkable claims the baseline made about environments it cleared are false | `python3 evaluation/refutations.py` | Any row reading "claim holds", or a count other than 6 of 6. |
| 7 | A confirmed verdict ships a working exploit | `./run.sh demo` | An exploit that does not actually pass, or no disagreement shown against the reference. |
| 8 | It reproduces from a clean clone | See section 5 below | Different numbers from a fresh clone. |
| 9 | **This documentation matches the committed evidence** | `python3 evaluation/check_docs.py` | Anything other than `RESULT: PASS`. 24 checks, described below. |

### On claim 9, which exists because this project failed it

A reviewer ran the sixty-second check in section 1 and got numbers different from
the ones this document told them to expect. They were right. `t15_safe_divide`
was relabelled from sound to broken late in the build, moving the corpus from
"8 broken, 7 sound" to "9 broken, 6 sound", and three documents were never
updated, including this one. The measurements were correct throughout; the prose
was stale.

For a project whose whole argument is *do not trust an assertion, execute
something*, publishing stale numbers in the file written for reviewers is the
worst available defect. Correcting the text was not enough, because nothing
prevented a recurrence the next time a label moved. So the invariant is now
enforced:

```bash
python3 evaluation/check_docs.py
```

It derives the corpus shape from `corpus/manifest.json` and every figure from
`evaluation/results/*.json`, then fails if a document states something the
evidence does not support:

- no document quotes a **detection rate** whose denominator disagrees with the
  corpus, so relabelling a task updates the expectation automatically
- no **balanced accuracy** appears in prose that is absent from a committed result
- `envguard/llm.py` and `run.sh` default to the **model** the results were
  actually measured with
- `trajectories/05-baseline-judge.md` agrees with `evaluation/results/v0.json`
- every changelog version has a **result file** behind it
- no document asserts the **retracted provenance claim** ("no number typed by
  hand") except where it is being withdrawn
- every **"N times slower"** multiplier is within 2% of a real ratio between two
  committed wall clocks

The last two were added after a second review round found `126x`, `~120x` and the
true `117x` coexisting in one README, and the retracted provenance claim still
live in three files after being withdrawn in a fourth. Both are the same defect
as the original: a correction applied in one place and not propagated. Both are
now mechanical.

It was tested the way everything else here is tested. Every finding from two
rounds of external review was reintroduced into a scratch copy to confirm the
checker fails on each: the stale detection rate, the stale balanced accuracy, the
wrong model default, the contradicting trajectory, the retracted provenance
claim, and two inconsistent multipliers. It catches all of them, failing 8 of its
24 checks. Removing them returns it to PASS.

The tolerance on the multiplier check is deliberately tight, at 2 percent. A
looser 5 percent band was written first and let a claimed `94x` pass against a
true `97x`, which is the exact near-miss the check exists to catch. That was
found by testing the checker rather than by reading it.

---

## 3. How to check I did not rig it

This is the part worth your time. A result is only meaningful if the setup was
fair, so here is how to attack the setup itself.

### Is the baseline deliberately weak?

Read `baseline/baseline.py`. Check that it uses:

- the **same model** as the full system (`DEFAULT_MODEL`, both default to `qwen3:4b`,
  which is the model every committed result in `evaluation/results/` was produced with)
- the **same corpus**, all 15 environments
- the **same structured output contract** (a JSON schema, so it cannot fail on formatting)
- a prompt that **explains what hackable means** and gives concrete examples

```bash
sed -n '/^SYSTEM_PROMPT/,/^"""$/p' baseline/baseline.py
```

The only thing the baseline lacks is the ability to execute code. That is the
variable under test. If you think the prompt is unfair, edit it and re-run
`--version v0`; the harness does not care what the prompt says.

### Is the corpus rigged so the templates trivially win?

The risk is that "sound" tasks were written to be unbeatable by construction and
"broken" ones to fall to the first template. Check both directions:

```bash
python3 evaluation/check_corpus.py
```

It executes every template against every task and asserts that **sound tasks
survive all of them**. Note it reports `no template is a universal harness
bypass (175 checked)`, meaning no single trick beats everything.

Then read the corpus yourself. It is 15 small files:

```bash
cat corpus/tasks/t11_is_palindrome/verifier.py    # sound, and only 4 assertions
cat corpus/tasks/t03_slugify/verifier.py          # broken, and looks completely normal
```

`t03_slugify` is the honest test of the premise: it reads like an ordinary test.
The baseline approved it. It is beaten by returning a string constant.

### Are the "broken" tasks actually broken?

`corpus/manifest.json` records a `reference_exploit` for each. Run one yourself:

```bash
python3 - <<'PY'
import sys, json; sys.path.insert(0, "envguard")
from sandbox import run_candidate
m = json.load(open("corpus/manifest.json"))
for t in m["tasks"]:
    if not t.get("reference_exploit"): continue
    v = open(f"corpus/tasks/{t['id']}/verifier.py").read()
    r = run_candidate(v, t["reference_exploit"])
    print(f"{t['id']:26s} exploit passes verifier: {r.passed}")
PY
```

Every line should print `True`. Those are wrong programs that the shipped
verifiers accept.

### Is the differential tester too lenient, or too strict?

It decides whether a candidate is genuinely wrong. Both failure directions
matter, so it is tested against both:

```bash
python3 envguard/differential.py
```

Expected: the reference solution and a correct-but-rewritten version report
`differs=False`; a constant stub and a length heuristic report `differs=True`.
If a correct program reported `differs=True`, the system would condemn sound
environments.

### Is anything hidden in the numbers?

The **generated** tables cannot be, and you can prove it. `evaluation/results.md`
and `evaluation/refutations.md` are rendered entirely from the committed JSON, so
regenerate them and diff:

```bash
python3 evaluation/make_report.py > /tmp/regenerated.md
diff /tmp/regenerated.md evaluation/results.md && echo "tables match the raw results"
```

> Run this **before** re-running any evaluation, or pass `--no-save` when you do.
> A re-run records a fresh wall-clock time into the result file, and the
> regenerated report will then differ by a second or two purely because your
> machine is not the machine that produced the committed numbers. That is a
> timing artefact, not a discrepancy in any claim. Every `run_eval.py` invocation
> accepts `--no-save` so that checking the evidence cannot alter the evidence.

**The README tables are a different matter, and weaker.** They are transcribed
from the generated files by hand, so they can be wrong, and twice they were: a
wall clock written as 883s where `v2` records 857.2s, and a six-row table that
had lost a row while still claiming "6 of 6". An earlier version of this document
told you no figure in the prose was typed by hand. That was itself false and is
retracted. The guard is `python3 evaluation/check_docs.py`, which fails when
prose contradicts the evidence. If you find a README number that disagrees with
`evaluation/results.md`, the generated file is right and that is a bug worth
reporting.

---

## 4. Read the raw evidence

```bash
python3 -c "
import json; d=json.load(open('evaluation/results/v4.json'))
r=[x for x in d['rows'] if x['task_id']=='t03_slugify'][0]
print(r['verdict']); print(r['evidence']['source']); print(r['evidence']['disagreements'])"
```

That prints the actual exploit and the concrete inputs where it computes a
different answer from the reference. Copy the exploit into
`corpus/tasks/t03_slugify/solution.py` and run the verifier yourself; it passes.

---

## 5. Reproduce from scratch, as a judge would

**The submitted archive is the artifact.** It is a `git archive` of the exact
commit, so it contains the committed tree and nothing else: no `.git`, no
`__pycache__`, no local scratch. Unzip it anywhere and run:

```bash
unzip envguard-<sha>.zip && cd envguard-<sha>
python3 envguard/sandbox.py
python3 evaluation/check_corpus.py
python3 evaluation/run_eval.py --version v3 --no-save
```

No clone, no network, no `pip install`, no API key, no Ollama for any of the
three. The v3 numbers must match `evaluation/results/v3.json` exactly: same
confusion matrix, same rates, same verdict on all 15 environments.

If you have access to the repository, the same check runs from a clone:

```bash
git clone https://github.com/Abdullah0157/envguard.git verify-envguard && cd verify-envguard
```

Both paths were performed and are documented under "Verified reproduction" in
`REPRODUCTION.md`. Nothing in this document depends on the clone succeeding.

---

## 6. Known limitations, stated so you can check them too

These are real and are not hidden in a footnote:

1. **The corpus is synthetic and small.** Fifteen environments, hand-authored.
   It is an exact answer key, which is what makes the numbers meaningful, but it
   is not a sample of micro1's production environments.
2. **The score measures reach on this corpus**, not that the problem is solved.
   Harder defect families would lower it, and one already does: `t15_safe_divide`
   is missed by every configuration and is reported as a miss rather than fixed.
3. **`CLEAN` means "resisted every attack we ran."** No finite test suite can be
   proven unhackable, because memorising its cases beats it.
3b. **The differential tester trusts `solution.py` as the oracle.** A candidate is
   convicted when it disagrees with the reference. The sanity gate catches a
   reference that fails its own verifier, but *not* a reference that is wrong in
   the same direction as its verifier, which is the common real-world case: an
   author misreads the spec and writes a solution and a test that agree with each
   other and are both wrong. In such an environment a genuinely correct candidate
   disagrees with the reference and would be reported `CONFIRMED_HACKABLE` with
   proof attached. This corpus cannot exhibit that failure because the references
   were authored here; SWE-bench does exhibit it. Related: the memorisation guard
   in `differential.py` is a **suppression channel**, so a true exploit that
   happens to compare against a literal the verifier tests is downgraded to
   coverage and the environment is reported `CLEAN`.
4. **The harness is forgeable.** A candidate that flushes a success marker and
   exits cleanly beats any in-process grader. envguard detects this with a canary
   and escalates, but detection is not prevention. The architectural fix is
   stated in the README as the main failure mode.
5. **The model stage is reproducible in distribution, not bit for bit.** Local
   inference varies with hardware. The headline result comes from the
   deterministic path, which does reproduce exactly.

If any of the above surprises you when you run it, that is a finding worth
raising, not a detail to overlook.
