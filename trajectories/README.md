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
| **Coding agent** | Claude Code, model Claude Opus 5 | Built this repository | shell, file editing, the project's own test suites |

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
| [`01-attacker-retracted.md`](01-attacker-retracted.md) | **The most instructive run, and the one that shows the retry loop learning.** Attempt 1 is rejected by the verifier; the failure is fed back verbatim and attempts 2 and 3 change strategy, both keying on the verifier's own test inputs. That is memorisation, which defeats every finite verifier and so says nothing about this one, and both claims are withdrawn. The environment is correctly reported sound. |
| [`02-template-confirmed.md`](02-template-confirmed.md) | A confirmed defect found with no inference at all. The verifier reads like an ordinary test and the read-only baseline approved it; a deterministic template beats it in under a second, and differential testing proves the exploit is genuinely wrong. |
| [`03-sanity-gate.md`](03-sanity-gate.md) | An environment that no attacker could ever flag, because its verifier rejects its own reference solution. Only running the reference first reveals it. This is the evidence that justifies stage one of the pipeline. |
| [`05-baseline-judge.md`](05-baseline-judge.md) | **The comparison the whole project is measured against.** One turn, no tools, and that absence is the variable under test. It reads the same task and verifier the attacker sees, reasons about the weakness accurately, and still concludes the environment is fine. |
| [`04-coding-agent.md`](04-coding-agent.md) | **The coding agent that built this repository.** Seven checkpoints where a tool response or a committed artefact contradicted the agent and changed the design: the harness bypass, a wrong answer key, a false confirmation, a fabricated measurement, a conclusion its own later data reversed, three defects found by external reviewers, and documentation that described a system the code no longer was. |

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
