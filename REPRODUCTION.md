# Reproduction guide

Written for someone starting from a clean machine with nothing installed.

> **This guide has been tested by following it literally.** The repository was
> cloned fresh from GitHub into an empty directory and every command below was
> run in order. All three verification steps passed, and `v3` reproduced the
> published result exactly: identical confusion matrix, identical rates, and
> identical verdicts on all 15 environments. See "Verified reproduction" at the
> end of this document.

There is **no API key, no billing account, and no `pip install` anywhere in this
guide**. Everything runs locally and offline after the model is pulled once.
Total cost to reproduce every number in this repository: **$0.00**.

---

## 1. Prerequisites

**To reproduce the headline result you need Python 3 and nothing else.**

The recommended configuration (`v3`) makes zero inference calls, so it needs no
model, no download, no API key, and no network. If you only want to check the
main claim, skip straight to section 5.

| Requirement | Needed for | Version used |
|---|---|---|
| **Python 3.10+** | **Everything. This is the only hard requirement.** | 3.14.6 |
| Ollama | Only the optional model stages (`v0`, `v1`, `v2`, `v4`) | 0.32.6 |
| ~6 GB disk | Only the model weights, if you run those stages | - |
| 16 GB RAM | Only the model stages. 8 GB is fine with `qwen3:4b` | - |

There are no Python dependencies. There is no virtual environment. There is no
`requirements.txt`, because there is nothing to require.

```bash
python3 --version      # 3.10 or newer. This is all you need for v3.
```

Running a model-backed configuration without Ollama fails with a clear message
pointing you at `--version v3` rather than a stack trace.

## 2. Get the model

```bash
ollama serve &            # skip if Ollama is already running
ollama pull qwen3:4b      # about 2.5 GB, one time. All committed results use this.
```

Confirm it is reachable:

```bash
curl -s http://localhost:11434/api/tags | head -c 200
```

**`qwen3:4b` is the default and you do not need to set anything.** Every
committed result in `evaluation/results/` was produced with it, and
`envguard/llm.py` defaults to it, so the model-backed changelog rows reproduce
with no environment variable at all. This was not always true: an earlier
version defaulted to `qwen3:8b` while every result used `4b`, which an external
reviewer correctly flagged as four changelog rows that would not reproduce with
documented defaults.

To use a different model anyway, set `ENVGUARD_MODEL`:

```bash
export ENVGUARD_MODEL=qwen3:8b     # not recommended on 16 GB; see the note below
```

`llama3.2:3b` and `qwen3:8b` were also tried. **Neither has a committed result
file**, so nothing in this repository's measured claims rests on them, and the
remarks about them below are stated as unlogged observations rather than
results.

> **On a 16 GB machine, prefer `qwen3:4b`.** Measured on this hardware, `qwen3:8b`
> resides at about 5.3 GB and pushed the system into swap (2.4 GB of swap in use,
> ~190k pageouts), which turned occasional inference calls into 200s+ outliers.
> `qwen3:4b` is about 2.5 GB and ran roughly 40% faster per call in the model
> comparison, with no measured loss on this task.
>
> This affects only the optional model stage. The deterministic stages, which is
> where all of the detection came from, never load a model at all:
>
> ```bash
> python3 evaluation/run_eval.py --version v3   # 8/10, 0.90, ~7s, no inference
> ```

## 3. Get the code

**If you have the submitted archive, use it. It is the artifact.** It is a
`git archive` of the exact commit, so it contains the committed tree and nothing
else: no `.git`, no `__pycache__`, no local scratch files. Everything below works
from it, and nothing below needs a network connection.

```bash
unzip envguard-<sha>.zip
cd envguard-<sha>
```

A clone works too, if you have access to the repository:

```bash
git clone https://github.com/Abdullah0157/envguard.git
cd envguard
```

> The repository may be private, in which case that clone will return 404 and
> **that is not a problem for reproducing anything**. Every command in this
> document runs from the unzipped archive. The clone is only useful if you want
> to inspect the commit history.

## 4. Verify the machinery before trusting any number

Run these in order. Each is fast and each guards a different assumption.
If any fails, stop: the results downstream would be meaningless.

```bash
python3 envguard/sandbox.py        # ~7s   22 isolation and edge-case checks
python3 evaluation/check_corpus.py # ~17s  the answer key is sound, proven by execution
python3 evaluation/check_docs.py   # <1s   the documentation matches the results
python3 envguard/llm.py            # ~30s  model reachable, JSON schema, exploit executes
```

Expected final lines:

```
sandbox self-test: PASS
RESULT: PASS - answer key is sound
RESULT: PASS - documentation matches the evidence (36 checks)
llm self-test: PASS
```

Only the last of those needs Ollama. The first three need Python 3 and nothing
else.

`check_corpus.py` is the important one. It proves by execution that every
"broken" environment really is beatable, that every "sound" environment resists
every deterministic attack, and that no attack is a universal harness bypass. The
detection rates reported later are only meaningful because this passes.

`check_docs.py` exists because this repository failed the check it performs. An
external reviewer ran the sixty-second check in `VERIFY.md`, got 8/9 at the time where the
document said to expect 8/8, and was right: a late corpus relabel had moved the
answer key without the prose following. That script now derives every figure from
`corpus/manifest.json` and `evaluation/results/*.json` and refuses to pass if any
document disagrees. **If you find a number in this repository that contradicts
the evidence, this script is the bug, and that is worth reporting.**

## 5. Reproduce the headline comparison

```bash
python3 evaluation/run_eval.py --version v0   # baseline, reads the verifier only
python3 evaluation/run_eval.py --version v4   # full envguard pipeline
python3 evaluation/make_report.py --write     # regenerate evaluation/results.md
```

Each writes `evaluation/results/<version>.json` containing every per-task
verdict, the exploit source where one was found, and the confusion matrix.
`make_report.py` renders `evaluation/results.md` from those files, and that file
is diffable against what is committed.

It does **not** render `README.md`. The README tables are transcribed by hand and
have been wrong twice, so an earlier version of this sentence, claiming no number
in the prose was typed by hand, was false and is retracted. `check_docs.py` is
the guard that replaced it.

## 6. Reproduce the full improvement changelog

Each row of the changelog is the same codebase with different stages enabled.

```bash
python3 evaluation/run_eval.py --version v0   # baseline: read, do not execute
python3 evaluation/run_eval.py --version v1   # model writes exploits, all executed
python3 evaluation/run_eval.py --version v2   # + gold sanity gate
python3 evaluation/run_eval.py --version v3   # + deterministic templates, no model
python3 evaluation/run_eval.py --version v4   # full: templates first, model on survivors
python3 evaluation/make_report.py --write
```

`python3 evaluation/run_eval.py --list` prints the configurations.

## 7. Approximate runtimes

> **These are idle-machine numbers and they are the least reproducible thing in
> this repository.** A reviewer measured `v3` at 28 to 33 seconds against the ~7
> below, and `check_corpus.py` at 76 seconds against ~25, on comparable hardware
> under load. Every verdict they got was identical to the committed one. Treat
> the table below as a lower bound, not a promise.

Measured on an Apple M1, 16 GB, `qwen3:4b`. Model-backed stages are slower on
`qwen3:8b`, which swaps on a 16 GB machine.

| Command | Runtime | Model calls |
|---|---|---|
| `sandbox.py` | ~7s (22 checks) | 0 |
| `check_corpus.py` | ~25s | 0 |
| `run_eval.py --version v3` | **~7s** | **0** |
| `run_eval.py --version v0` | ~4 min | 15 |
| `run_eval.py --version v4` | ~15 min | 8 |
| `run_eval.py --version v1` | ~15 min; the model runs on every environment | 18 |

v3 is the one worth noticing: it audits all 15 environments in about seven
seconds without invoking a language model at all. Timings vary by machine; the
committed result files record what this one measured.

## 8. Determinism

Every model call is seeded from `(task index, attempt number)` and runs at
temperature 0, and the probe inputs used for differential testing are a fixed,
ordered list. Re-running the same version should reproduce the same verdicts.

Local inference is not bit-for-bit guaranteed across different hardware or
Ollama versions, so treat the deterministic stages (`v3`, `check_corpus.py`)
as the exactly reproducible core and the model stages as reproducible in
distribution.

## 9. What you should see

- `v0`, the read-only baseline, finds **2 of 10** defects for a balanced accuracy
  of 0.60. It describes each weakness accurately and concludes the environment is
  fine anyway.
- `v3` finds **8 of 10** with **0 false alarms** in about seven seconds and zero
  model calls.
- Both miss `t15_safe_divide`. That is expected and documented; it is a defect
  this system cannot detect, kept in the corpus and reported rather than removed.
- Any `CONFIRMED_HACKABLE` verdict includes the exploit source and the concrete
  inputs on which it disagrees with the reference solution. You can paste that
  exploit into the environment yourself and watch it pass.

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ERROR: no Ollama server` | Ollama not running | `ollama serve` |
| `ERROR: model ... not installed` | weights not pulled | `ollama pull qwen3:4b` |
| `llm self-test` fails on JSON | model emitting reasoning blocks | ensure `think: false`; already set in `envguard/llm.py` |
| Very slow model stages | 8B model on a small machine | `export ENVGUARD_MODEL=qwen3:4b` |
| `sandbox self-test` fails | non-POSIX platform | resource limits are POSIX only; the timeout still applies |

---

## Verified reproduction

This is not a claim that the guide *should* work. It was executed.

**Method.** A fresh `git clone` of this repository into an empty directory on a
machine that had never run it, then every command in sections 4 and 5 above, in
order, with no edits and no steps skipped.

**Result.**

| Step | Command | Outcome |
|---|---|---|
| 4a | `python3 envguard/sandbox.py` | `sandbox self-test: PASS` (22 checks) |
| 4b | `python3 evaluation/check_corpus.py` | `RESULT: PASS - answer key is sound` |
| 4c | `python3 envguard/llm.py` | `llm self-test: PASS`, model-written exploit executed and confirmed |
| 5 | `python3 evaluation/run_eval.py --version v3` | 8/10 found, 0/5 false alarms, balanced accuracy 0.90, ~7s, 0 model calls |

Step 5 printed, verbatim:

```
  detected        8/10 broken environments
  false alarms    0/5 clean environments
  recall          0.80
  specificity     1.00
  precision       1.00
  BALANCED ACC    0.90   (always-say-hackable scores 0.50)
  wall clock      6.7s for 15 environments
  model calls     0
  cost            $0.00 (local inference)
  misses:
    - t13_normalize_whitespace   MISSED DEFECT: Survived 14 executed attack(s).
    - t15_safe_divide            MISSED DEFECT: Survived 14 executed attack(s).
```

**Numbers matched the published run exactly.** Every field of the confusion
matrix, every derived rate, and the verdict on all 15 environments were
identical between the fresh clone and the committed `evaluation/results/v3.json`:

```
[ok] true_positives       8        (committed 8)
[ok] false_positives      0        (committed 0)
[ok] true_negatives       5        (committed 5)
[ok] false_negatives      2        (committed 2)
[ok] recall               0.8      (committed 0.8)
[ok] specificity          1.0      (committed 1.0)
[ok] precision            1.0      (committed 1.0)
[ok] balanced_accuracy    0.9      (committed 0.9)
[ok] 15/15 per-task verdicts identical
     differing: none
```

The two false negatives are `t13_normalize_whitespace` and `t15_safe_divide`.
Both are **known and reported misses**, not reproduction failures: the published
result is 8/10 and a machine that had never seen this repository also gets 8/10.
A run that printed 10/10 would be the surprising outcome.

The deterministic path carries no dependency on wall-clock time, randomness, or
network access, which is why every verdict and every derived rate reproduces
exactly.

**Not byte for byte, and the distinction matters.** Each result file records a
`wall_clock_s`, which is machine-dependent, so `evaluation/results/v3.json` will
differ from the committed copy in that one field on any machine that is not the
one that produced it. The confusion matrix, every rate, and the verdict on all 15
environments are identical. An earlier version of this sentence claimed byte-for-
byte reproduction, which a reviewer correctly called false. Pass `--no-save` if
you want to check the evidence without altering it. The optional model
stages are reproducible in distribution rather than exactly, because local
inference varies with hardware and Ollama version; this is stated in section 8
and is why the headline result is drawn from the deterministic path.

> **An external reviewer re-ran `v0` against their own local Ollama and got all
> 15 verdicts identical to the committed file**, including the exact miss list
> and the two it finds. So on this corpus the model-backed path reproduced
> exactly, not merely in distribution. That is a stronger result than the claim
> above, and the claim is deliberately left as the weaker one: one matching
> re-run on similar hardware does not establish determinism across machines,
> Ollama versions or quantisations. Reported because it is evidence the
> self-reported baseline was not cherry-picked from a bad run.
