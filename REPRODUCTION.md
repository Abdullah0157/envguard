# Reproduction guide

Written for someone starting from a clean machine with nothing installed.

There is **no API key, no billing account, and no `pip install` anywhere in this
guide**. Everything runs locally and offline after the model is pulled once.
Total cost to reproduce every number in this repository: **$0.00**.

---

## 1. Prerequisites

| Requirement | Version used | Notes |
|---|---|---|
| Python | 3.14.6 | Standard library only. Any Python 3.10+ works; nothing to install. |
| Ollama | 0.32.6 | Runs the local model. https://ollama.com/download |
| Disk | ~6 GB | For the model weights. |
| RAM | 16 GB | Measured on an Apple M1 with 16 GB. 8 GB is enough for `qwen3:4b`. |

There are no Python dependencies. There is no virtual environment. There is no
`requirements.txt`, because there is nothing to require.

```bash
python3 --version      # 3.10 or newer
ollama --version       # any recent version
```

## 2. Get the model

```bash
ollama serve &            # skip if Ollama is already running
ollama pull qwen3:8b      # about 5.2 GB, one time
```

Confirm it is reachable:

```bash
curl -s http://localhost:11434/api/tags | head -c 200
```

To use a different model, set `ENVGUARD_MODEL`. `qwen3:4b` and `llama3.2:3b`
were also measured; see the ablation in `README.md`.

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
git clone <repository-url> micro1-env-auditor
cd micro1-env-auditor
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

Measured on an Apple M1, 16 GB, `qwen3:8b`.

| Command | Runtime | Model calls |
|---|---|---|
| `sandbox.py` | ~7s | 0 |
| `check_corpus.py` | ~17s | 0 |
| `run_eval.py --version v3` | **~7s** | **0** |
| `run_eval.py --version v0` | ~80s | 15 |
| `run_eval.py --version v4` | several minutes | tens |
| `run_eval.py --version v1` | longest; the model runs on every environment | tens |

v3 is the one worth noticing: it audits all 15 environments in about seven
seconds without invoking a language model at all.

## 8. Determinism

Every model call is seeded from `(task index, attempt number)` and runs at
temperature 0, and the probe inputs used for differential testing are a fixed,
ordered list. Re-running the same version should reproduce the same verdicts.

Local inference is not bit-for-bit guaranteed across different hardware or
Ollama versions, so treat the deterministic stages (`v3`, `check_corpus.py`)
as the exactly reproducible core and the model stages as reproducible in
distribution.

## 9. What you should see

- `v0` flags **every** environment as hackable, sound ones included, for a
  balanced accuracy of 0.50, which is what an always-say-yes classifier scores.
- `v3` reaches a perfect score on this corpus in about seven seconds with zero
  model calls.
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
