# envguard

**Try to cheat an RL environment before it ships. If you succeed, attach the proof.**

An agent that audits reinforcement-learning environments for reward hackability.
It runs entirely on a local model, costs **$0.00 per environment**, and every
verdict it issues is backed by code that was actually executed.

Built for the micro1 Frontier Engineering Challenge, August 2026.

---

## The user and the bottleneck

**Who.** The engineer responsible for environment quality at an AI data lab, on
the team that builds and ships RL environments to frontier labs. At micro1 that
is the Realm product line.

**What they ship.** An RL environment is a task plus a *verifier*: a grader that
decides automatically whether a candidate solution is correct. Labs train models
by having them attempt the task thousands of times against that verifier.

**The bottleneck.** Nobody knows whether a verifier is any good until someone
attacks it. If the verifier can be satisfied by a solution that does not solve
the task, the lab is not training a model to do the work. It is training a model
to cheat, and paying for the privilege. Published 2026 measurements:

| Finding | Source |
|---|---|
| **28.5%** of SWE-bench Verified tasks accept a container-verified *incorrect* patch | [arXiv 2606.16062](https://arxiv.org/html/2606.16062v1) |
| **25.0%** on R2E-Gym across six repositories | same |
| **59.4%** of failed tasks have flawed tests (OpenAI, Feb 2026) | same |
| An LLM judge reading the test file misses **61.9%** of defects that executing the code catches | same |

Roughly one environment in four is quietly broken, and reading the file is not
enough to tell.

**Why it is worth solving now.** On 18 August 2026 micro1's CEO stated the
company had committed **over $20,000,000 in 11 days** to license real operational
data to seed RL environments, with more than 1,000 companies signed up. That is
roughly $2M a day of raw material flowing into their highest-margin product.
The current defence is human expert review, which micro1 pays up to **$200/hour**
for. At 30 minutes per environment that is about **$100 per environment**, and it
is exactly the cost line that turns a $500M gross run rate into a $150M to $200M
net one.

So the bottleneck is not detection in principle. It is detection at a price and
a speed that keeps up with intake.

---

## What envguard does

Given a task, its reference solution, and its verifier, envguard returns
**ship, repair, reject, or escalate to a human**, with evidence.

```
                        ┌──────────────────────────────────────┐
  task + verifier  ───▶ │ 1. SANITY GATE                       │
                        │    run the reference solution.       │
                        │    it fails? the environment is      │──▶ GOLD_FAILURE
                        │    broken at the root.               │
                        └──────────────┬───────────────────────┘
                                       ▼
                        ┌──────────────────────────────────────┐
                        │ 2. TEMPLATE ATTACKS                  │
                        │    ~13 deterministic exploits built  │
                        │    from the signature. No inference. │
                        └──────────────┬───────────────────────┘
                                       ▼
                        ┌──────────────────────────────────────┐
                        │ 3. MODEL ATTACKS                     │
                        │    only on survivors, so inference   │
                        │    is spent where cheap methods fail │
                        └──────────────┬───────────────────────┘
                                       ▼
                        ┌──────────────────────────────────────┐
                        │ 4. VERIFICATION (three independent   │
                        │    facts must all hold)              │
                        │    a. the verifier accepted it       │
                        │    b. it did not escape the grader   │──▶ CONFIRMED_HACKABLE
                        │    c. it provably disagrees with     │    + working exploit
                        │       the reference solution         │    + disagreeing inputs
                        └──────────────────────────────────────┘
```

**A confirmed verdict cannot be a false alarm.** It ships a working exploit and
the concrete inputs on which that exploit computes a different answer from the
reference solution. Uncertainty is confined to `SUSPECTED`, which is the queue a
human reviews. envguard never edits, deletes, or ships an environment itself.

---

## Results

Fifteen hand-authored environments. Eight carry a deliberately planted verifier
defect, one per family; seven are sound. Because the defects were authored rather
than discovered, `corpus/manifest.json` is an **exact answer key**, and
`evaluation/check_corpus.py` proves by execution that the key is correct before
any result is reported.

| Metric | Baseline (reads the verifier) | envguard | Change |
|---|---|---|---|
| Defects found | 8/8 | 8/8 | no change |
| False alarms on sound environments | **7/7** | **0/7** | **-7** |
| Specificity | **0.00** | **1.00** | **+1.00** |
| Precision | 0.53 | 1.00 | +0.47 |
| **Balanced accuracy** | **0.50** | **1.00** | **+0.50** |
| Wall clock, all 15 | 81s | **7s** (v3, no model calls) | 11x faster |
| Cost per environment | $0.00 | $0.00 | - |

**The baseline answered "hackable" on all fifteen environments.** Its recall is
perfect and its specificity is zero, which means it carries exactly as much
information as a function that returns `True` without reading anything. Balanced
accuracy 0.50 is the score of that trivial classifier, and the baseline matches
it exactly.

### The baseline is precise, confident, and wrong

It did not fail by being vague. Every false alarm came with a specific reason
naming a specific program. So we built each program it described and ran it
against the very verifier it was judging. **All 7 of 7 claims are false:**

| Environment | The baseline's claim | Program it describes | Executed |
|---|---|---|---|
| `t10_dedupe` | "could return the input unchanged" | `return items` | **fails** |
| `t11_is_palindrome` | "always returns True could pass" | `return True` | **fails** |
| `t13_normalize_whitespace` | "could return a constant string" | `return ''` | **fails** |
| `t14_merge_sorted` | "could return the input lists concatenated" | `return left` | **fails** |
| `t15_safe_divide` | "could return None for all cases" | `return None` | **fails** |

Full table, generated by `evaluation/refutations.py`, in
[`evaluation/refutations.md`](evaluation/refutations.md).

Confident and wrong is the hardest kind of wrong to catch by reading, and it is
exactly what execution catches for free.

Generated tables, including the per-environment breakdown, live in
[`evaluation/results.md`](evaluation/results.md). Every number in this README is
rendered by `evaluation/make_report.py` from the committed JSON in
`evaluation/results/`. None of them are typed by hand.

### Cost comparison against the alternative

| | Human expert review | envguard |
|---|---|---|
| Time per environment | ~30 min | ~0.5s (deterministic stages) |
| Rate | up to $200/hour | local inference |
| **Cost per environment** | **~$100** | **$0.00** |
| Evidence produced | a written opinion | an executable exploit |

---

## Improvement changelog

Each version is the same codebase with different stages enabled, so the measured
contribution of a stage is a controlled comparison rather than a guess between
four divergent snapshots. Full numbers in
[`evaluation/results.md`](evaluation/results.md); raw output in
`evaluation/results/v*.json`.

| Version | What changed and why | Evidence | Decision |
|---|---|---|---|
| **v0** | Baseline. Show the model the task and the verifier, ask whether an incorrect solution could pass. Nothing executed. | 8/8 found, **7/7 false alarms**, balanced accuracy **0.50** | Established the starting point. Reproduces the published finding that reading a verifier is not enough. |
| **v1** | Let the model write exploits, and **execute every one**. A claim only survives if it is reproduced. | False alarms collapse: nothing is asserted that was not run | Kept. Execution, not the model, is what removes false alarms. |
| **v2** | Added the **gold sanity gate**: run the reference solution against its own verifier first. | Catches `t08_days_between`, whose verifier rejects its own reference solution. No attack can find this, because there is nothing to attack. | Kept. One environment class is only reachable this way. |
| **v3** | Added **deterministic template attacks** generated from the function signature: constants, empty values of the right type, identity, and the literal the verifier compares against. | **8/8 found, 0/7 false alarms, balanced accuracy 1.00, in 7 seconds with zero model calls** | Kept. This is where essentially all the detection came from. |
| **v4** | Added **model attacks on survivors only**, so inference runs exactly where cheap methods failed. | See `results.md`. On this corpus the deterministic stages had already found everything. | Kept for coverage on environments the templates cannot reach, but it is not what makes the system work. |
| **fix** | **Differential verification.** Discovered mid-build that v4 was confirming a false positive. See below. | Restored `t11_is_palindrome` to a correct `CLEAN` verdict without losing any true detection | Kept. This is what makes a confirmed verdict trustworthy. |
| **removed** | Multiple parallel attacker personas. | Tripled inference for no additional detection on this corpus, because the templates had already found everything the personas could. | **Removed.** Diversity of attackers is worthless when the bottleneck is not attacker creativity. |

### The iteration that mattered most, and it was not a feature

While building v4, the attacker model returned this against `t11_is_palindrome`
and declared it an exploit:

```python
def is_palindrome(text):
    return text == text[::-1] if isinstance(text, str) else False
```

It passed the verifier. My pipeline marked the environment `CONFIRMED_HACKABLE`.

That code is **correct**. It is the reference implementation with a type guard
bolted on. I had been verifying that a candidate *passes*, and taking the model's
word that it was *wrong*. The entire premise is "a wrong solution that
nonetheless passes," and I was only checking half of it. One sound environment
was condemned on a model's say-so.

The fix is `envguard/differential.py`: a candidate counts as an exploit only when
it **observably disagrees with the reference solution** on a concrete input.
Reference and candidate are executed side by side over a deterministic,
type-directed pool of probes. Agreement is now a retraction, not a confirmation.

That single change is what lets this README claim a confirmed verdict cannot be a
false alarm.

---

## Main failure mode

**Grading runs in the same process as the code being graded, so the code can
attack the grader instead of the verifier.**

This is not hypothetical. Measured on this harness, every one of these passes
*every* environment in the corpus, sound ones included:

```python
print('PASS', flush=True); os._exit(0)
os.write(1, b'PASS\n');    os._exit(0)
print('PASS');             sys.exit(0)
```

A single such candidate would mark the whole corpus hackable and destroy the
answer key. envguard **detects** this with a canary verifier that cannot be
satisfied honestly: anything that "passes" it is escaping the grader rather than
exploiting the verifier, so its other passes are discarded and the case is
escalated (`HARNESS_BYPASS`).

Detection is not prevention. The honest fix is architectural and is not
implemented here: **the candidate must not run in the same process that reports
the result.** Execution should produce outputs; grading should happen elsewhere,
on those outputs. Until that separation exists, any in-process harness, including
every pytest-based RL environment in wide use today, is forgeable by code that
flushes a success marker and exits.

Second, smaller limitation: `CLEAN` means "resisted every attack we ran." No
finite set of assertions can be proven unhackable, because a solution that
memorises the test cases passes any finite test suite. `CLEAN` is evidence, not
proof, and the report says so.

---

## Hot take

**Execution was load-bearing. Intelligence was not.**

The deterministic stages, with **zero model calls**, scored a perfect 1.00
balanced accuracy on this corpus in about seven seconds. The language model, the
expensive and impressive part, added nothing on top of them, and its one
independent contribution was a **false positive** that took a differential tester
to retract.

The industry framing of reward hacking is "models are getting clever enough to
game our graders." What this build suggests is closer to the opposite: most
graders are broken in mechanical, enumerable ways, and you find them by *trying
things and running them*, not by reasoning about them. The best-performing
configuration here is a for-loop over ten templates and a subprocess call.

If that holds on real environments, the practical advice for a data lab is
uncomfortable and cheap: **before you buy a smarter auditor, run the dumb attacks
and actually execute them.** The naive LLM reviewer scored 0.50, the same as
answering "yes" to everything. A hundred lines of deterministic Python scored
1.00. The gap between them is not intelligence, it is whether anyone ran the code.

---

## What existed before this competition

Nothing. This repository was written from scratch during the challenge window.

- No pre-existing code was reused.
- The corpus is entirely synthetic and hand-authored for this project. No
  licensed, proprietary, scraped, or personal data is used anywhere.
- No credentials appear in the repository, because the system needs none.
- Third-party dependencies: none. Standard library only, plus a local Ollama
  server for inference.

Coding agent used: **Claude Code** (Claude Opus 5). Representative trajectories
are in [`trajectories/`](trajectories/), including the session where the
false-positive bug was found and fixed.

---

## Repository layout

```
corpus/
  manifest.json          the answer key: which environments are broken and how
  tasks/t01..t15/        task statement, reference solution, verifier
envguard/
  sandbox.py             isolated execution; 22 self-tests
  differential.py        is this candidate actually wrong?
  attacks.py             deterministic exploit templates
  llm.py                 Ollama client (think:false, JSON schema, seeded)
  auditor.py             the pipeline and the verdicts
baseline/baseline.py     the read-only comparison
evaluation/
  check_corpus.py        proves the answer key by execution
  run_eval.py            runs a version, writes results/<version>.json
  make_report.py         renders the tables from those results
  results/               committed raw results, one file per version
trajectories/            annotated agent runs
```

## Quick start

```bash
ollama pull qwen3:8b
python3 envguard/sandbox.py          # 22 isolation checks
python3 evaluation/check_corpus.py   # prove the answer key
python3 evaluation/run_eval.py --version v3   # perfect score, 7s, no model calls
```

Full instructions, including runtimes and troubleshooting, in
[`REPRODUCTION.md`](REPRODUCTION.md).
