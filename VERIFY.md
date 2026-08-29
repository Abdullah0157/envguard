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
detected        8/8 broken environments
false alarms    0/7 clean environments
BALANCED ACC    1.00   (always-say-hackable scores 0.50)
wall clock      ~7s for 15 environments
model calls     0
```

If that prints 8/8 and 0/7, the central claim holds: the system finds every
planted defect and falsely accuses nothing, without calling a language model.

---

## 2. Claim by claim

| # | Claim in README | Command that checks it | What proves it false |
|---|---|---|---|
| 1 | The sandbox really isolates and really detects | `python3 envguard/sandbox.py` | Anything other than `sandbox self-test: PASS`. 22 checks including timeouts, print bombs, orphaned processes, and forged success tokens. |
| 2 | The answer key is correct, not just asserted | `python3 evaluation/check_corpus.py` | Anything other than `RESULT: PASS`. It executes every task to prove broken ones are beatable and sound ones are not. |
| 3 | The baseline scores 0.50, same as always saying yes | `python3 evaluation/run_eval.py --version v0` | A balanced accuracy meaningfully above 0.50. |
| 4 | envguard scores 1.00 with zero model calls | `python3 evaluation/run_eval.py --version v3` | Fewer than 8/8 found, or any false alarm, or a nonzero model call count. |
| 5 | Adding the model *on top of* templates yields +0 detections | `python3 evaluation/run_eval.py --version v4`, compare to v3 | v4 finding a defect that v3 missed. |
| 5b | The model is redundant, **not** incapable: it finds 8/8 unaided, just 126x slower | `python3 evaluation/run_eval.py --version v2`, compare to v3 | v2 scoring below 8/8, which would mean the README oversells the model rather than the templates. |
| 6 | All 7 baseline claims about sound environments are false | `python3 evaluation/refutations.py` | Any row reading "passes (claim holds)". |
| 7 | A confirmed verdict ships a working exploit | `./run.sh demo` | An exploit that does not actually pass, or no disagreement shown against the reference. |
| 8 | It reproduces from a clean clone | See section 5 below | Different numbers from a fresh clone. |

---

## 3. How to check I did not rig it

This is the part worth your time. A result is only meaningful if the setup was
fair, so here is how to attack the setup itself.

### Is the baseline deliberately weak?

Read `baseline/baseline.py`. Check that it uses:

- the **same model** as the full system (`DEFAULT_MODEL`, both default to `qwen3:8b`)
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

No figure in the prose is typed by hand. Regenerate every table from the raw
results and diff it:

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

```bash
cd /tmp && rm -rf verify-envguard
git clone https://github.com/Abdullah0157/envguard.git verify-envguard
cd verify-envguard
python3 envguard/sandbox.py
python3 evaluation/check_corpus.py
python3 evaluation/run_eval.py --version v3
```

The v3 numbers must match `evaluation/results/v3.json` exactly: same confusion
matrix, same rates, same verdict on all 15 environments. This was performed and
is documented under "Verified reproduction" in `REPRODUCTION.md`.

---

## 6. Known limitations, stated so you can check them too

These are real and are not hidden in a footnote:

1. **The corpus is synthetic and small.** Fifteen environments, hand-authored.
   It is an exact answer key, which is what makes the numbers meaningful, but it
   is not a sample of micro1's production environments.
2. **A perfect score means the corpus was within reach**, not that the problem is
   solved. Harder defect families would lower it.
3. **`CLEAN` means "resisted every attack we ran."** No finite test suite can be
   proven unhackable, because memorising its cases beats it.
4. **The harness is forgeable.** A candidate that flushes a success marker and
   exits cleanly beats any in-process grader. envguard detects this with a canary
   and escalates, but detection is not prevention. The architectural fix is
   stated in the README as the main failure mode.
5. **The model stage is reproducible in distribution, not bit for bit.** Local
   inference varies with hardware. The headline result comes from the
   deterministic path, which does reproduce exactly.

If any of the above surprises you when you run it, that is a finding worth
raising, not a detail to overlook.
