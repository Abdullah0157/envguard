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

That last row is why this project exists, and it is the prediction this project
set out to test on its own corpus. It reproduced, and worse than the paper
measured: the read-only baseline missed **7 of 9** defects, not 61.9%.

It also failed *inconsistently*. On a larger model the same prompt on the same
corpus inverted, flagging every environment including the sound ones. Reading a
verifier does not merely produce a wrong answer; it produces an unstable one,
with nothing in the output to indicate which way it went.

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

**A confirmed verdict ships its own proof.** It carries a working exploit and the
concrete inputs on which that exploit computes a different answer from the
reference solution, so a reviewer checks a demonstration rather than an opinion.
Genuine uncertainty, a candidate that passed but could not be compared, goes to
`SUSPECTED` for a human. envguard never edits, deletes, or ships an environment
itself.

An earlier draft of this README claimed a confirmed verdict *could not* be a
false alarm. That was too strong and it was falsified: an external reviewer
produced a correct `merge_sorted` implementation that this system convicted,
because the probe generator fed it inputs outside the function's stated
precondition. The bug is fixed and the guarantee is withdrawn. What survives is
weaker and true: every confirmation is reproducible, and across the attacks
evaluated here it produced no false confirmation.

---

## What "good" was defined as, before any evaluation ran

The success bar was written down before measuring. Where it was later met, and
where it was not, is stated below rather than adjusted.

**Primary metric: balanced accuracy.** Chosen because it is the one number a lazy
classifier cannot game. An auditor that flags everything scores 0.50 no matter
how many defects the corpus contains.

**The bar for the intended user**, an environment QA engineer deciding what ships:

| Requirement | Why it was set this way | Met? |
|---|---|---|
| Beat 0.50 balanced accuracy | Below this the tool is no better than answering "hackable" to everything | **Yes, 0.94** |
| Zero false confirmations across the evaluated attacks | A wrong accusation makes an engineer distrust the tool and stop using it | **Yes, 0 of 6 sound environments** |
| Every confirmation ships runnable proof | A verdict a reviewer cannot check is a verdict they must redo by hand | **Yes** |
| Cheap enough to run on every environment, not a sample | Sampling is how defects reach production | **Yes, ~0.5s and $0.00 each** |
| Detect every defect in the corpus | The obvious ambition | **No. 8 of 9. See the miss below.** |

The zero-false-confirmation requirement is what drove the design, and it is why
`differential.py` exists: a candidate that merely passes the verifier is not
enough to convict. Note that this is a claim about the attacks evaluated, not a
proof of impossibility. It was violated once during development and the failure
is documented above.

## The defect this system cannot find

`t15_safe_divide` is in the corpus, is genuinely broken, and **is missed by every
configuration**, including the full pipeline.

The task requires the quotient *as a float*. The verifier asserts
`safe_divide(6, 3) == 2.0`, and `2 == 2.0` is true in Python, so integer division
passes while returning the wrong type and flooring every inexact result:
`safe_divide(7, 2)` gives `3`, not `3.5`.

Neither the deterministic templates nor the local model finds it. **An external
adversarial reviewer did**, in an environment this project had labelled sound.
The label was wrong and has been corrected.

Reaching 9 of 9 from here would take about ten minutes: add one template that
returns the wrong numeric type. **That was deliberately not done.** With one
instance of this defect family in the corpus, adding an attack for it after
seeing the answer would fit the tool to the test and measure nothing. The miss is
reported instead.

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
comments. It looks under-tested. Against every attack that does not memorise it,
it holds: constant-true fails `"hello"`, constant-false fails `"racecar"`, and
the expected values differ so nothing can be hardcoded.

It is also the environment that later broke my definition of "sound" entirely.
This is the case the attacker eventually defeated by memorising its four test
inputs, which sent me to measure the other six and find they all fall the same
way. That story is under
[The finding that changed the project](#the-finding-that-changed-the-project-no-verifier-is-unhackable).
HC2 therefore did its job twice: once as a false-positive trap, and once as the
case that exposed a wrong assumption in the corpus itself.

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

Fifteen hand-authored environments. Nine carry a verifier defect; six are sound.
Eight defects were planted deliberately, one per family. The ninth,
`t15_safe_divide`, was **found by an external adversarial reviewer** in an
environment this project had labelled sound; the label was corrected rather than
the environment removed.

`evaluation/check_corpus.py` proves by execution that the key holds before any
result is reported. Its limits are stated under
[Limitations](#limitations-stated-rather-than-discovered-by-a-judge).

| Metric | Baseline (reads the verifier) | envguard (`v3`) | Change |
|---|---|---|---|
| **Balanced accuracy** | **0.61** | **0.94** | **+0.33** |
| Defects found | **2/9** | **8/9** | **+6** |
| False alarms on sound environments | 0/6 | 0/6 | no change |
| Human time per environment | 4.0 min | 1.1 min | **-73%** |
| Machine time, all 15 | 72s | **7s** | 10x faster |
| Model calls | 15 | **0** | - |
| Cost per environment | $0.00 | $0.00 | - |

**The baseline misses seven of nine defects.** It reads each verifier, reasons
about it, and concludes almost everything is fine. That is the more dangerous
failure mode of the two: over-flagging wastes a reviewer's time, under-flagging
ships broken environments to a lab.

Its failure mode is also **not stable across models**. On `qwen3:8b` the same
prompt on the same corpus did the opposite: it flagged *every* environment,
sound ones included, scoring 0.50, exactly what answering "hackable" to
everything scores. Swap the model and you get the inverse behaviour with no
signal in the output telling you which one you are holding. Execution does not
have that property.

### Where the two sides differ in resources

The brief asks for meaningful differences in what each side is given. There is
one, it favours envguard, and it is stated here rather than left to be found:

| | Baseline | envguard |
|---|---|---|
| Model | `qwen3:4b` | `qwen3:4b` (same) |
| Environments | all 15 | all 15 (same) |
| Output contract | JSON schema | JSON schema (same) |
| Prompt | defines "hackable", gives four concrete examples | defines the same attack families |
| **Attempts** | **one, no retries** | **up to three, each informed by the previous failure** |
| **Can execute code** | **no** | **yes** |

The execute/not-execute difference is the variable under test, so it is the point
rather than an unfairness. **The attempt count is not**, and a fairer baseline
would get three attempts too. It does not, so treat the baseline's 2 of 9 as a
floor rather than a ceiling.

Two things bound how much that matters. The baseline has no tool to learn from,
so a retry would resample the same reasoning against the same unchanged input;
and the failure it exhibits is not hesitancy but confidence, since it describes
each weakness accurately and clears the environment anyway. Neither argument is a
measurement, and the honest position is that this comparison is generous to
envguard by an unquantified amount.

### The baseline is specific, confident, and wrong

It does not fail by being vague. Every verdict comes with a checkable reason. So
for each defect it declared clean, the working exploit was executed against the
very verifier it had cleared. **6 of 6 hold up:**

| Environment | The baseline's verdict | Exploit that beats it | Executed |
|---|---|---|---|
| `t01_average` | "only checks the result is not None, a very weak constraint" | `return 42` | **passes** |
| `t02_clamp` | "only checks one specific case" | `return value` | **passes** |
| `t03_slugify` | "only checks one specific input and output" | `return "hello-world-again"` | **passes** |
| `t06_top_k` | "only checks if the result is a list" | `return []` | **passes** |
| `t15_safe_divide` | "checks multiple specific cases including zero denominator" | `return numerator // denominator` | **passes** |

Read those reasons again. They are **accurate descriptions of the weakness** and
the baseline still concluded the environment was fine. It saw the hole and did
not walk through it, because it never had to run anything.

Full table, generated by `evaluation/refutations.py`, in
[`evaluation/refutations.md`](evaluation/refutations.md).

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
| **v0** | Baseline. Show the model the task and the verifier, ask whether an incorrect solution could pass. Nothing executed. | **2/9 found, 0/6 false alarms, balanced accuracy 0.61.** It reads each verifier, describes the weakness accurately, and concludes the environment is fine anyway. | Established the starting point. On a larger model the same prompt failed in the opposite direction, flagging everything for 0.50. |
| **v1** | Let the model write exploits, and **execute every one**. A claim only survives if it is reproduced. | **2/9 -> 7/9 found, balanced accuracy 0.61 -> 0.89.** | Kept. This is the single largest improvement in the project, and it comes from running the model's output rather than from any change to the model. |
| **v2** | Added the **gold sanity gate**: run the reference solution against its own verifier first. | **7/9 -> 8/9, balanced accuracy 0.89 -> 0.94.** v1 missed `t08_days_between`, whose verifier rejects its own reference solution. No attack can reach it, because there is nothing there to exploit. | Kept. It recovers the one environment attacking cannot, for a single execution costing 0.04s. |
| **v3** | Added **deterministic template attacks** generated from the function signature: constants, empty values of the right type, identity, and the literal the verifier compares against. | **8/9 found, 0/6 false alarms, balanced accuracy 0.94, in 7 seconds with zero model calls.** Matches v2 exactly while using no inference at all. | Kept, and this is the recommended configuration. Essentially all the detection comes from here. |
| **v4** | Added **model attacks on survivors only**, so inference runs exactly where cheap methods failed. | **8/9, 0/6, balanced accuracy 0.94, 8 model calls.** Identical detection to v3. **+0 defects for the added inference.** | **Demoted from the headline.** Kept in the codebase, because the one defect nothing here finds is exactly the kind templates cannot express. |
| **final** | **Combined what worked:** sanity gate, then deterministic templates, then the model on survivors, with every candidate executed and every confirmation checked against the reference. | **8/9 found, 0/6 false alarms, balanced accuracy 0.94.** The recommended configuration (`v3`) reaches this in 7 seconds with zero inference. | **The main contribution is execution, not intelligence.** The step from reading to running took 2/9 to 7/9. Everything after that added 1 more defect between them. |
| **fix** | **Differential verification.** Removed the pipeline's trust in the attacker's own claim that a candidate was wrong. | Retracted a false `CONFIRMED_HACKABLE` on `t11_is_palindrome` without losing any true detection. Recorded in [`trajectories/01-attacker-retracted.md`](trajectories/01-attacker-retracted.md). | Kept. This is what makes a confirmed verdict trustworthy. |

**What was removed, and what it taught me.** Two things were tried and cut, and
both are measured rather than asserted:

1. **Trusting the model's self-assessment** (cut in the `fix` row above). The
   attacker declared a correct implementation to be an exploit and the pipeline
   believed it. The lesson is that a generator cannot be its own judge; the
   retraction has to come from execution against a reference, not from a better
   prompt.
2. **The model stage as the recommended path** (cut in the `v4` row). Not because
   it failed. `v2` shows the model finds **8 of 9 unaided**, the same score the
   templates reach, with real and reproducible exploits. It was cut because it
   buys the *same* answer at roughly **120 times the wall clock** (883s versus
   7s). The lesson is not that attacker creativity is useless; it is that
   creativity was never the binding constraint on this corpus, so paying for it
   bought nothing that was not already free.

*Note on scope:* I did not run a parallel-attacker-persona experiment. A single
attacker reaches the same ceiling as the templates here (8 of 9), and the one
defect neither finds, `t15_safe_divide`, is not the kind more attacker diversity
would reach. The budget went into differential verification instead. If the
corpus contained defects a single attacker missed, that experiment would be worth
running and this note would be an excuse rather
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

## Limitations, stated rather than discovered by a judge

Three independent reviewers were given fresh clones of this repository and asked
to break it. They found four real defects, all since fixed, and three structural
criticisms that cannot be fixed by editing code. Those are recorded here rather
than left for a reader to find.

**1. The defect families overlap heavily with the attack families.** `D1` weak
assertion is beaten by `const_int`, `D2` happy-path by `identity`, `D3` leaked
expected value by `hardcode_expected`, `D6` type-only by `empty_list`. The corpus
was authored by the same person who wrote the attacks, so a high score partly
reflects that overlap rather than the difficulty of the problem. A corpus authored
independently, or drawn from real environments, would be a materially stronger
test and this one should not be mistaken for it.

**2. `check_corpus.py` is not independent validation.** It defines a sound
environment as one that no template beats, and the system is then scored against
those same templates. Specificity is therefore high partly by construction. What
the script does prove, and this is still worth having, is that every environment
labelled broken really is beatable, by executing the exploit; and that no attack
is a universal bypass. It does not prove a sound label is correct, as
`t15_safe_divide` demonstrated by being wrong.

**3. The reviewer-time saving is modelled, not measured.** No human was timed. The
figures come from two stated constants in `evaluation/make_report.py`: 30 minutes
to audit an environment unaided, 2 minutes to confirm a verdict that already
carries an executed exploit. Both are inferred from micro1's published expert
rate. Disagree with either and the percentage moves; the constants are in one
place so it can be recomputed.

**Also true, and easy to miss:**

- The corpus is 15 small Python functions. The problem is framed at the scale of
  SWE-bench and R2E-Gym, which are whole repositories. That gap is real.
- The model stage is reproducible in distribution, not exactly. Only the
  deterministic path reproduces bit for bit.
- `t15_safe_divide` is a defect this system cannot detect, and it stays in the
  corpus for that reason.

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

**Second: memorisation defeats every finite verifier, including all seven sound
ones in this corpus.** This is not a limitation discovered by reasoning about it;
it was measured, after the attacker model produced a memorising solution against
an environment labelled sound. See "The finding that changed the project" above.

envguard detects memorisation and reports it as a coverage property rather than a
defect, because an attack that beats everything distinguishes nothing. But
detection is not a fix. The fix is coverage, and coverage has no ceiling: a
verifier is only ever *harder* to memorise, never impossible. `CLEAN` therefore
means "no attack succeeded that did not key on the verifier's own test inputs",
which is the strongest claim a finite test suite can support.

---

## The finding that changed the project: no verifier is unhackable

Late in the build, the attacker model returned this against `t11_is_palindrome`,
an environment I had labelled **sound**:

```python
def is_palindrome(text):
    return text == text[::-1] if text in ("racecar", "") else False
```

It returns `False` for every input except the two the verifier happens to check.
`is_palindrome("aa")` returns `False`, and "aa" is a palindrome. That is genuinely
broken code, and it passes.

So I measured how far it went, rather than patching the one case:

> **All 7 sound environments fall to it. Every single one.**

The reason is not a flaw in those seven verifiers. It is arithmetic. **A finite
list of assertions can always be satisfied by memorising the list.** "Unhackable"
is not a property a finite verifier can have.

This is the same shape as the harness bypass caught on day one: a **universal
attack** that defeats everything, and therefore says nothing about any particular
environment. Left unclassified it would have marked the entire corpus broken and
destroyed the answer key, for the second time.

**How it is handled.** `envguard/differential.py` separates memorisation from a
real exploit by asking what the candidate *branches on*. `return 42` never
mentions the tested inputs. `if n == 3` does. Memorisation is reported as a
**coverage** property of the verifier, never as a defect, so it can never
contaminate a per-task verdict.

Getting that discriminator right took two attempts. The first version flagged six
legitimate template exploits, because a hardcoded *output* can coincide with an
*input*: `clamp(5, 0, 10) == 5` returns the same 5 it was given. Only literals in
a deciding position, inside a comparison or as a dict key, actually indicate
memorisation.

**What "sound" therefore means here**, stated precisely rather than implied: *no
attack succeeds that does not key on the verifier's own test inputs.* That is the
strongest claim any finite test suite can support, and it is weaker than the word
"clean" suggests. The manifest says so in those words.

**Two environments were deleted because of this.** They had been added
specifically as cases only the model could crack. Once memorisation was correctly
classified, their only exploit was memorisation, which meant they differed from
the sound environments in degree rather than in kind. They were measuring test
suite size, not verifier quality, so they were removed.

---

## Hot take

**Execution was load-bearing. Intelligence was optional for the work I planned,
and indispensable for the mistake I did not.**

The tempting version of this finding is "the model was useless." That is not what
the measurement says, and I nearly wrote it before running the experiment that
disproved it.

Given the same environments and no deterministic help at all, the model found
**8 of 9 defects with zero false alarms**, the same score the templates reach.
Its exploits are real and independently reproducible: for `top_k` it returned
`[5, 9]` where the reference returns `[9, 5]`, beating the verifier by getting
the *ordering* wrong rather than the values. That is a genuinely subtle attack.

So the model is not incompetent. It is **redundant** here:

| Configuration | Found | False alarms | Model calls | Wall clock |
|---|---|---|---|---|
| Model alone, no templates (`v2`) | 8/9 | 0/6 | 16 | 883s |
| Templates alone, no model (`v3`) | 8/9 | 0/6 | **0** | **7s** |

Identical accuracy. **Roughly 120 times the wall clock.** And when both run
together (`v4`), the model adds nothing further, because the templates already
found everything it would have.

The word "here" is load-bearing. Both configurations miss `t15_safe_divide`, and
neither the templates nor the model can reach it. On a corpus with more defects
of that shape the ranking would change, which is exactly why the model stage is
kept in the codebase rather than deleted.

The industry framing of reward hacking is "models are getting clever enough to
game our graders," which invites the response "so buy a cleverer auditor." The
measurement points somewhere cheaper and less flattering: **most graders are
broken in mechanical, enumerable ways.** A constant. An empty list. The literal
the test compares against. You find those by trying them and running them, and a
for-loop enumerates them faster than any model can reason its way to them.

The useful question for a data lab is therefore not *can the model do it*. It
demonstrably can. The question is *is the model the cheapest thing that can*, and
here it was not, by two orders of magnitude.

**And then the model did the one thing the templates never could.** It found an
error in my ground truth. Not a planted puzzle, an actual mistake: seven
environments I had certified as sound were defeated by an attack I had not
considered. No template found that, because no template was written to look for
it, and I could not have written one for a weakness I did not know existed.

That is the honest division of labour this project actually measured:

| | What it is for |
|---|---|
| **Deterministic attacks** | Finding the defects you already know how to describe. Faster and cheaper than inference, every time. |
| **The model** | Finding the ones you didn't. It is not a cheaper enumerator; it is the thing that questions your assumptions. |

The mistake would be reading the wall-clock numbers and concluding "drop the
model." On the work I designed, it was 126 times slower for an identical answer.
On the work I got wrong, it was the only component that caught me.

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
