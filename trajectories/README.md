# Agent trajectories

Representative runs for every agent used in this project, each readable from the
agent's instructions through to the final result, showing what the agent did, how
its tools responded, what that feedback changed, and where a human decides.

**None of these are written by hand.** `envguard/auditor.py` accepts a `trace`
argument that records every step of a real run; `capture.py` renders those
recordings into the documents below. Regenerate them with:

```bash
python3 trajectories/capture.py
```

---

## The agents in this system

| Agent | Where it lives | Instructions | Tools it can call |
|---|---|---|---|
| **Attacker** | `envguard/auditor.py` (`ATTACKER_SYSTEM`) | Write a solution that is wrong for the task but still passes the verifier | sandbox execution, harness-bypass canary, differential tester |
| **Baseline judge** | `baseline/baseline.py` (`SYSTEM_PROMPT`) | Read the task and verifier, decide whether an incorrect solution could pass | none, by design |

Both prompts are committed in full and are quoted verbatim inside the
trajectories, so nothing about how the agents were steered is hidden.

The **deterministic attacker** in `envguard/attacks.py` is not a model. It is
included in the trajectories because it is the component that does almost all of
the actual work, and pretending the language model was responsible would
misrepresent the system.

---

## The trajectories

| File | What it shows |
|---|---|
| [`01-attacker-retracted.md`](01-attacker-retracted.md) | **The most instructive run.** The attacker produces a program that passes the verifier and claims it is an exploit. Execution disagrees, the claim is retracted, and the environment is correctly declared sound. Shows retries, feedback between attempts, and the checkpoint that protects a human from a false accusation. |
| [`02-template-confirmed.md`](02-template-confirmed.md) | A confirmed defect found with no inference at all. The verifier reads like an ordinary test and the read-only baseline approved it; a deterministic template beats it in under a second, and differential testing proves the exploit is genuinely wrong. |
| [`03-sanity-gate.md`](03-sanity-gate.md) | An environment that no attacker could ever flag, because its verifier rejects its own reference solution. Only running the reference first reveals it. This is the evidence that justifies stage one of the pipeline. |

---

## How to read them

Each trajectory follows the same shape:

1. **What the agent was given** - the task, the verifier under audit, and the
   agent's verbatim instructions.
2. **Step by step** - every tool call and its real response. Model attempts show
   the feedback carried forward from the previous failure, so you can see the
   loop adapting rather than retrying blindly.
3. **Outcome** - the verdict, the evidence attached to it, and what a human is
   asked to do.

Look for the blocks marked **Human-facing checkpoint**. Those are the points
where the system declines to act on its own conclusion.

---

## The agent that built this

The repository itself was written with **Claude Code** (Claude Opus 5). Two
findings from that session are documented in `README.md` because they changed the
design rather than just the code:

- the harness-bypass discovery, where a candidate that flushes a success token and
  exits was found to pass *every* environment including sound ones, which would
  have destroyed the answer key
- the false-positive discovery, where the attacker returned the reference
  implementation with a type guard, called it an exploit, and was believed

The second of those is the run captured in `01-attacker-retracted.md`.
