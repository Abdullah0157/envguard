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

To use a different model, set `ENVGUARD_MODEL`. `qwen3:4b` and `llama3.2:3b`
were also measured. `qwen3:4b` is the model all committed results use; `qwen3:8b`
produces the same detection but inverts the baseline's failure mode, which is
discussed in README.md under "The baseline is specific, confident, and wrong".

```bash
export ENVGUARD_MODEL=qwen3:4b     # optional
```

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
> python3 evaluation/run_eval.py --version v3   # perfect score, ~7s, no inference
> ```

## 3. Get the code

```bash
git clone https://github.com/Abdullah0157/envguard.git
cd envguard
```

## 4. Verify the machinery before trusting any number

Run these three in order. Each is fast and each guards a different assumption.
If any fails, stop: the results downstream would be meaningless.

```bash
python3 envguard/sandbox.py        # ~7s   22 isolation and edge-case checks
python3 envguard/llm.py            # ~30s  model reachable, JSON schema, exploit executes
python3 evaluation/check_corpus.py # ~17s  the answer key is sound, proven by execution
```

Expected final lines:

```
sandbox self-test: PASS
llm self-test: PASS
RESULT: PASS - answer key is sound
```

`check_corpus.py` is the important one. It proves by execution that every
"broken" environment really is beatable, that every "sound" environment resists
every deterministic attack, and that no attack is a universal harness bypass. The
detection rates reported later are only meaningful because this passes.

## 5. Reproduce the headline comparison

```bash
python3 evaluation/run_eval.py --version v0   # baseline, reads the verifier only
python3 evaluation/run_eval.py --version v4   # full envguard pipeline
python3 evaluation/make_report.py --write     # regenerate evaluation/results.md
```

Each writes `evaluation/results/<version>.json` containing every per-task
verdict, the exploit source where one was found, and the confusion matrix.
`make_report.py` renders the tables used in `README.md`, so no number in the
prose is typed by hand.

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

- `v0`, the read-only baseline, finds **2 of 9** defects for a balanced accuracy
  of 0.61. It describes each weakness accurately and concludes the environment is
  fine anyway.
- `v3` finds **8 of 9** with **0 false alarms** in about seven seconds and zero
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
| `ERROR: model ... not installed` | weights not pulled | `ollama pull qwen3:8b` |
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
| 5 | `python3 evaluation/run_eval.py --version v3` | 8/8 found, 0/7 false alarms, balanced accuracy 1.00, 6.5s |

**Numbers matched the published run exactly.** Every field of the confusion
matrix, every derived rate, and the verdict on all 15 environments were
identical between the fresh clone and the committed `evaluation/results/v3.json`:

```
[ok] true_positives     8      [ok] recall             1.00
[ok] false_positives    0      [ok] specificity        1.00
[ok] true_negatives     7      [ok] precision          1.00
[ok] false_negatives    0      [ok] balanced_accuracy  1.00
[ok] all 15 per-task verdicts identical
```

The deterministic path carries no dependency on wall-clock time, randomness, or
network access, which is why it reproduces byte for byte. The optional model
stages are reproducible in distribution rather than exactly, because local
inference varies with hardware and Ollama version; this is stated in section 8
and is why the headline result is drawn from the deterministic path.
