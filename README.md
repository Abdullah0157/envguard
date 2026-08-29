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
| **59.4%** of failed tasks have flawed tests (OpenAI, Feb 2026) | reported in the same work |
| A gold-sanity gate that *executes* code caught **61.9%** of test defects that an LLM judge alone missed | [arXiv 2606.16062](https://arxiv.org/html/2606.16062v1) |

Roughly one environment in four is quietly broken, and reading the file is not
enough to tell.

That last row is why this project exists, and it is also the prediction this
project set out to test on its own corpus. The result was stronger than the
paper's: our read-only baseline did not miss 61.9% of defects, it misclassified
**every sound environment in the corpus**, scoring exactly what a function that
always answers "hackable" would score.

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

## What "good" was defined as, before any evaluation ran

The corpus, the answer key, and the success bar were fixed before the first
measurement, so the bar could not be moved to fit the result.

**Primary metric: balanced accuracy.** Chosen because it is the one number a
lazy classifier cannot game. An auditor that flags everything scores 0.50 no
matter how many defects the corpus contains, which is exactly the failure mode a
nervous reviewer falls into.

**The bar for the intended user**, an environment QA engineer deciding what ships:

| Requirement | Why it was set this way | Met? |
|---|---|---|
| Beat 0.50 balanced accuracy | Below this, the tool is no better than always saying "hackable" | Yes, 1.00 |
| **Zero false confirmations** | A wrong accusation makes an engineer distrust the tool and stop using it. This is stricter than "high precision": a confirmed verdict must be impossible to be wrong | Yes, 0/7 |
| Every confirmation ships runnable proof | A verdict a reviewer cannot check is a verdict they must redo by hand | Yes |
| Cheap enough to run on every environment, not a sample | Sampling is how defects reach production | Yes, ~0.5s and $0.00 each |

The zero-false-confirmation requirement is the one that drove the design. It is
why the differential tester exists, and it is why a candidate that merely passes
the verifier is not enough to convict.

## The two hard cases, and what they revealed

The brief asks for a challenging case. There are two, one in each direction,
because a tool that only ever errs one way is easy to fake.

**HC1, `t03_slugify` (broken, but reads as completely normal).** A single
assertion comparing against one expected string. It is the most ordinary-looking
file in the corpus. **What it revealed:** the read-only baseline approved it, and
so would most humans skimming a batch. It falls in 0.5 seconds to a template that
returns the literal the test compares against. Plausibility and correctness are
unrelated properties, and only execution separates them.

**HC2, `t11_is_palindrome` (sound, but reads as thin).** Four assertions, no
comments. It looks under-tested. It is not: constant-true fails `"hello"`,
constant-false fails `"racecar"`, and the expected values differ so nothing can
be hardcoded.

**What HC2 revealed was the most important finding in the build.** The attacker
model produced this and declared it an exploit:

```python
def is_palindrome(text):
    return text == text[::-1] if isinstance(text, str) else False
```

It passes the verifier, so the pipeline confirmed the environment as hackable.
But that code is **correct**, the reference implementation with a type guard. A
sound environment was condemned because I was verifying that a candidate *passes*
and taking the model's word that it was *wrong*.

HC2 is the reason `envguard/differential.py` exists. Without a case designed to
look guilty while being innocent, that bug ships silently and every confirmation
in this report becomes untrustworthy.

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
| **v1** | Let the model write exploits, and **execute every one**. A claim only survives if it is reproduced. | **7/8 found, false alarms 7/7 -> 0/7, balanced accuracy 0.50 -> 0.94.** Every false alarm disappeared the moment claims had to be reproduced. | Kept. Execution, not the model, is what removes false alarms. This single change is worth more than everything after it. |
| **v2** | Added the **gold sanity gate**: run the reference solution against its own verifier first. | **7/8 -> 8/8, balanced accuracy 0.94 -> 1.00.** v1 missed exactly one environment, `t08_days_between`, and it is the one whose verifier rejects its own reference solution. No attack can reach it, because there is nothing there to exploit. | Kept. It recovers the single environment attacking cannot, and costs one execution (0.04s). |
| **v3** | Added **deterministic template attacks** generated from the function signature: constants, empty values of the right type, identity, and the literal the verifier compares against. | **8/8 found, 0/7 false alarms, balanced accuracy 1.00, in 7 seconds with zero model calls** | Kept. This is where essentially all the detection came from. |
| **v4** | Added **model attacks on survivors only**, so inference runs exactly where cheap methods failed. | 8/8 found, 0/7 false alarms, **19 model calls and 660s**, versus v3's 0 calls and 7s. **+0 detections.** | **Demoted.** Kept in the codebase for environments templates cannot reach, but removed from the recommended configuration. The headline reports v3. |
| **fix** | **Differential verification.** Removed the pipeline's trust in the attacker's own claim that a candidate was wrong. | Retracted a false `CONFIRMED_HACKABLE` on `t11_is_palindrome` without losing any true detection. Recorded in [`trajectories/01-attacker-retracted.md`](trajectories/01-attacker-retracted.md). | Kept. This is what makes a confirmed verdict trustworthy. |

**What was removed, and what it taught me.** Two things were tried and cut, and
both are measured rather than asserted:

1. **Trusting the model's self-assessment** (cut in the `fix` row above). The
   attacker declared a correct implementation to be an exploit and the pipeline
   believed it. The lesson is that a generator cannot be its own judge; the
   retraction has to come from execution against a reference, not from a better
   prompt.
2. **The model stage as the recommended path** (cut in the `v4` row). Not because
   it failed. `v2` shows the model finds **8/8 unaided**, with real and
   reproducible exploits. It was cut because it buys the *same* answer as the
   templates at **126x the wall clock** (882s versus 7s). The lesson is not that
   attacker creativity is useless; it is that creativity was never the binding
   constraint on this corpus, so paying for it bought nothing you did not already
   have for free.

*Note on scope:* I did not run a parallel-attacker-persona experiment. A single
attacker already reaches the ceiling on this corpus (8/8), so additional
attackers have no headroom to demonstrate, and the budget went into differential
verification instead. If the corpus contained defects a single attacker missed,
that experiment would be worth running and this note would be an excuse rather
than a reason.

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

**Execution was load-bearing. Intelligence was optional, and it was the expensive
way to buy the same answer.**

The tempting version of this finding is "the model was useless." That is not what
the measurement says, and I nearly wrote it before running the experiment that
disproved it.

Given the same environments and no deterministic help at all, the local 8B model
found **every single planted defect, 8 out of 8, with zero false alarms**. Its
exploits are real and independently reproducible: for `top_k` it returned
`[5, 9]` where the reference returns `[9, 5]`, beating the verifier by getting
the *ordering* wrong. That is a genuinely subtle attack.

So the model is not incompetent. It is **redundant**:

| Configuration | Found | False alarms | Model calls | Wall clock |
|---|---|---|---|---|
| Model alone, no templates (`v2`) | 8/8 | 0/7 | 26 | 882s |
| Templates alone, no model (`v3`) | 8/8 | 0/7 | **0** | **7s** |

Identical accuracy. **126 times the wall clock.** And when both run together
(`v4`), the model contributes nothing further, because the templates have already
found everything, while still costing 19 calls and 94x the time.

The industry framing of reward hacking is "models are getting clever enough to
game our graders," which invites the response "so buy a cleverer auditor." The
measurement points somewhere cheaper and less flattering: **most graders are
broken in mechanical, enumerable ways.** A constant. An empty list. The literal
the test compares against. You find those by trying them and running them, and a
for-loop enumerates them faster than any model can reason its way to them.

The useful question for a data lab is therefore not *can the model do it*. It
demonstrably can. The question is *is the model the cheapest thing that can*, and
here it was not, by two orders of magnitude.

One caveat I will not paper over: this corpus is small, synthetic, and its defect
families are exactly the enumerable kind. On defects that are not enumerable, the
ranking would likely invert, and the model stage is kept in the codebase for
precisely that reason. What the evidence supports is narrower and more actionable
than "skip the model": **run the cheap deterministic attacks first, and make the
model earn the environments they could not crack.**

---

## What existed before this competition

Nothing. This repository was written from scratch during the challenge window.

- No pre-existing code was reused.
- The corpus is entirely synthetic and hand-authored for this project. No
  licensed, proprietary, scraped, or personal data is used anywhere.
- No credentials appear in the repository, because the system needs none.
- Third-party dependencies: none. Standard library only, plus a local Ollama
  server for inference.

### Disclosure of agent use

**Tool: Claude Code, model Claude Opus 5.** Coding-agent use is required by this
challenge, so this is stated in full rather than minimised.

Claude Code was used across the whole project, not only for writing code:

| Stage | Agent's role | Human's role |
|---|---|---|
| Problem selection | Researched micro1's current products, funding and public statements; proposed five candidate problems with tradeoffs | Chose this one, rejected the other four |
| Corpus design | Authored the 15 environments and the defect taxonomy | Set the constraint that the answer key had to be provable |
| Implementation | Wrote all code in `envguard/`, `baseline/`, `evaluation/` | Directed scope, demanded edge-case coverage |
| Evaluation | Ran every configuration, generated all tables | Required independent verification of every claim |
| Documentation | Wrote README, REPRODUCTION, VERIFY, trajectories | Reviewed and ran the checks |

The external research that anchors the problem statement is cited inline: the
28.5% and 61.9% figures come from [arXiv 2606.16062](https://arxiv.org/html/2606.16062v1),
and the $20M/11-days figure is a public statement by micro1's CEO dated
18 August 2026.

**What the agent got wrong.** Four claims in earlier drafts were false and were
caught and corrected before submission: a fabricated experiment result, a
paraphrased citation that overstated its source, a headline that contradicted the
project's own generated tables, and a conclusion that a later measurement
reversed. Each correction is a separate commit with its reasoning in the message,
and the sequence is documented in
[`trajectories/04-coding-agent.md`](trajectories/04-coding-agent.md).

That record is included deliberately. A submission produced with an agent and
presented as flawless would be less trustworthy than one that shows where the
agent was wrong and what caught it.

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
git clone https://github.com/Abdullah0157/envguard.git && cd envguard
python3 envguard/sandbox.py                   # 22 isolation checks
python3 evaluation/check_corpus.py            # prove the answer key
python3 evaluation/run_eval.py --version v3   # perfect score, ~7s
```

**Those three commands need Python 3 and nothing else.** No API key, no
`pip install`, no virtual environment, no model download, no network. The
recommended configuration makes zero inference calls, so the result this project
most wants checked is also the cheapest one to check.

Ollama is needed only for the optional model-backed stages (`v0`, `v1`, `v2`,
`v4`). Running one of those without it fails with a message pointing you back to
`--version v3`, not a stack trace.

## Do not trust this README

Every claim here is checkable, and [`VERIFY.md`](VERIFY.md) pairs each one with
the command that would **disprove** it if it were false. It also shows how to
attack the setup itself: whether the baseline was made deliberately weak, whether
the corpus was rigged so the templates trivially win, whether the "broken"
environments really are broken, and whether any number in the prose was typed by
hand rather than generated.

Start here if you are evaluating this project:

```bash
python3 evaluation/run_eval.py --version v3   # ~7s, no model needed
```

## Reproducibility, verified rather than claimed

This repository was cloned fresh from GitHub into an empty directory, and every
command in [`REPRODUCTION.md`](REPRODUCTION.md) was run in order with nothing
skipped. All three verification steps passed, and `v3` reproduced the published
result **exactly**: identical confusion matrix, identical rates, and identical
verdicts on all 15 environments.

```
[ok] true_positives   8    [ok] recall            1.00
[ok] false_positives  0    [ok] specificity       1.00
[ok] true_negatives   7    [ok] precision         1.00
[ok] false_negatives  0    [ok] balanced_accuracy 1.00
[ok] all 15 per-task verdicts identical
```

The deterministic path depends on no wall clock, no randomness, and no network,
which is why it reproduces byte for byte. Full method and output under
"Verified reproduction" in [`REPRODUCTION.md`](REPRODUCTION.md).
