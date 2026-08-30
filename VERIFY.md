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
detected        8/10 broken environments
false alarms    0/5 clean environments
recall          0.80
specificity     1.00
precision       1.00
BALANCED ACC    0.90   (always-say-hackable scores 0.50)
wall clock      ~7s for 15 environments
model calls     0
cost            $0.00 (local inference)
misses:
  - t13_normalize_whitespace   MISSED DEFECT: Survived 14 executed attack(s).
  - t15_safe_divide            MISSED DEFECT: Survived 14 executed attack(s).
```

If that prints 8/10 and 0/5, the central claim holds: the system finds eight of
the ten defects and falsely accuses nothing, without calling a language model.
Two of those ten were not planted: they were found by external reviewers in
environments labelled sound, and both are among the misses.

**Both reported misses are deliberate.** `t15_safe_divide` was found to be broken by
an external adversarial reviewer, in an environment this project had labelled
sound. It was relabelled rather than deleted, and no attack was written for it,
because fitting an attack to a known answer measures nothing. If your run prints
`8/10` with `t13_normalize_whitespace` and `t15_safe_divide` in the misses list,
that is the expected result and not a degraded one. Both were found by external
reviewers in environments this project had labelled sound, both labels were
corrected, and no attack was written for either. See "The two defects this system
cannot find" in the README.

---

## 2. Claim by claim

| # | Claim in README | Command that checks it | What proves it false |
|---|---|---|---|
| 1 | The sandbox really isolates and really detects | `python3 envguard/sandbox.py` | Anything other than `sandbox self-test: PASS`. 22 checks including timeouts, print bombs, orphaned processes, and forged success tokens. |
| 2 | The answer key is correct, not just asserted | `python3 evaluation/check_corpus.py` | Anything other than `RESULT: PASS`. It executes every task to prove broken ones are beatable and sound ones are not. |
| 3 | The plain read-only baseline finds 2 of 10 at 0.60 | `python3 evaluation/run_eval.py --version v0` | A balanced accuracy meaningfully above 0.60, or more than 2 defects found. |
| 3b | **A much stronger read-only prompt does far better, and the README says so.** Reading is not the binding constraint the original headline implied | `python3 evaluation/run_eval.py --version v0-hardened` | This scoring at or below `v0`, which would mean the correction in the README overstates the baseline. An external reviewer reached 0.83 with their own prompt on the corpus as it then stood; mine reaches 0.60 on the corrected corpus. |
| 4 | envguard scores 0.90 with zero model calls, missing exactly `t13_normalize_whitespace` and `t15_safe_divide` | `python3 evaluation/run_eval.py --version v3` | Fewer than 8/10 found, any false alarm, a nonzero model call count, or a *different* task in the misses list. |
| 5 | Adding the model *on top of* templates yields +0 detections | `python3 evaluation/run_eval.py --version v4`, compare to v3 | v4 finding a defect that v3 missed. |
| 5b | The model is **not** incapable: unaided it finds 7 of 10, one fewer than the templates and ~120x slower | `python3 evaluation/run_eval.py --version v2`, compare to v3 | v2 scoring at or above 8/10, which would mean the README undersells the model. |
| 6 | All 6 checkable claims the baseline made about environments it cleared are false | `python3 evaluation/refutations.py` | Any row reading "claim holds", or a count other than 6 of 6. |
| 7 | A confirmed verdict ships a working exploit | `./run.sh demo` | An exploit that does not actually pass, or no disagreement shown against the reference. |
| 8 | It reproduces from a clean clone | See section 5 below | Different numbers from a fresh clone. |
| 9 | **This documentation matches the committed evidence** | `python3 evaluation/check_docs.py` | Anything other than `RESULT: PASS`. 34 checks, described below. |

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
- every **"N times slower"** multiplier agrees with a real ratio between two
  committed wall clocks
- **no verifier in the corpus contains a comment or docstring**, because a
  verifier is the artefact under audit and prose inside one hands the answer to
  any read-only reader
- a **hardened read-only baseline is committed**, and the README reports its score

Those were added across three review rounds, each closing the class of defect a
reviewer had just demonstrated rather than only the instance. The multiplier and
provenance checks came from a round that found `126x`, `~120x` and `117x`
coexisting in one README. The verifier-comment check came from a round that found
`t08_days_between` explaining its own defect in a three-line comment, which was
real contamination: with the comment a read-only baseline flags it every time,
without it never.

It is tested the way everything else here is tested. Every finding from all three
review rounds has been reintroduced into a scratch copy to confirm the checker
fails on each, then removed to confirm it passes.

**Two of its own checks were wrong and were caught the same way.** The multiplier
tolerance started at 5 percent, which let a claimed `94x` pass against a true
`97x`, the exact near-miss it exists to catch. Tightened to 2 percent, it then
failed on *correct* prose, because wall clock is machine-dependent: `v3` has been
recorded at both 7.3s and 6.8s, which moves the same ratio from 117 to 126 with
nothing about the system changing. It was enforcing precision the measurement
cannot support. It now allows 15 percent, and the documents quote one approximate
multiplier rather than tracking timing noise. Separately, the detection-rate check
flagged a legitimate `0/9` (an earlier corpus shape) because it assumed any `0/N` must be a false-alarm
rate; it now keys on the denominator alone.

---

## 3. How to check I did not rig it

This is the part worth your time. A result is only meaningful if the setup was
fair, so here is how to attack the setup itself.

### Is the baseline deliberately weak?

**Yes, the original one was, and this is the most important check on the page.**
An external reviewer wrote their own read-only prompt and scored far above `v0`,
which showed that most of the headline gap this project had been reporting was a
property of my prompt rather than of execution. The response is
`baseline/baseline.py`'s `HARDENED_SYSTEM_PROMPT`, committed and measured as
`v0-hardened`:

```bash
python3 evaluation/run_eval.py --version v0-hardened
```

It enumerates the corpus's own defect taxonomy, tells the model to be suspicious,
and demands it name a concrete attack before deciding. Same model, same corpus,
same seeds, same schema, no execution. Read both prompts and judge whether the
hardened one is genuinely strong; if you think you can do better, edit it and
re-run, since the harness does not care what the prompt says. The full correction,
including the two attempts that scored *worse* than the weak baseline, is under
Results in the README.

Then check that both use:

- the **same model** as the full system (`DEFAULT_MODEL`, both default to `qwen3:4b`,
  which is the model every committed result in `evaluation/results/` was produced with)
- the **same corpus**, all 15 environments
- the **same structured output contract** (a JSON schema, so it cannot fail on
  formatting). Note that this contract is **not neutral**: the field order inside
  it changes the result more than most prompt edits do. Same schema mechanism,
  `reason` before `hackable` instead of after, and the baseline goes from 2/10 at
  0.60 to flagging **all 15 environments**, 10 broken and 5 sound, at 0.50.
  Committed as `evaluation/results/v0-reason-first.json`
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
wall clock written as 883s where `v2` had recorded 857.2s at the time, and a six-row table that
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
