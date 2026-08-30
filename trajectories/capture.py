"""Capture agent trajectories from real runs.

The competition requires representative trajectories for every agent used, each
readable from the agent's instructions through to the final result, showing what
the agent did, how its tools responded, and what that feedback changed.

Nothing here is written by hand. Every trajectory in this directory is produced
by instrumenting `envguard.auditor.audit` and recording what actually happened.

Usage:
    python3 trajectories/capture.py            # regenerate all trajectories
    python3 trajectories/capture.py --task t11_is_palindrome
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "envguard"))

from auditor import ATTACKER_SYSTEM, audit  # noqa: E402
from corpus import load_tasks  # noqa: E402

OUT_DIR = os.path.join(ROOT, "trajectories")

# Each entry: (task id, filename, title, why this trajectory is worth reading,
#              whether to run the model stage)
SELECTED = [
    (
        "t11_is_palindrome",
        "01-attacker-retracted.md",
        "Attacker agent: three attempts, two claims withdrawn, correct final verdict",
        "The most instructive run in the project, and the one that shows the retry "
        "loop actually learning. Attempt 1 returns True and is rejected by the "
        "verifier. The failure is fed back verbatim, and attempts 2 and 3 change "
        "strategy: both key on the exact inputs the verifier tries. That is "
        "memorisation, a universal attack that defeats every finite verifier and "
        "therefore says nothing about this one, so both claims are withdrawn and the "
        "environment is correctly reported CLEAN. An earlier version of this loop "
        "returned a byte-identical wrong answer on all three attempts, because the "
        "feedback said only that the attempt had failed and discarded the reason.",
        True,
    ),
    (
        "t03_slugify",
        "02-template-confirmed.md",
        "Deterministic attacker: confirmed defect with executed proof, no inference",
        "The hard case. This verifier reads like a perfectly ordinary single-case "
        "test, and the read-only baseline approved it. A template that returns the "
        "literal the verifier compares against passes immediately, and differential "
        "testing proves the program is genuinely wrong. No model was involved.",
        False,
    ),
    (
        "t08_days_between",
        "03-sanity-gate.md",
        "Sanity gate: an environment no attacker could ever flag",
        "This verifier rejects its own reference solution, so there is nothing to "
        "exploit and every attack would fail, making the environment look sound. "
        "Only running the reference solution first reveals it. This is the evidence "
        "that justifies stage one of the pipeline.",
        False,
    ),
]


def render(task, title: str, rationale: str, trace: list, report) -> str:
    lines = [
        f"# {title}\n",
        "_Captured from a real run by `trajectories/capture.py`. Not written by hand._\n",
        f"\n**Why this trajectory:** {rationale}\n",
        f"\n**Environment:** `{task.id}`  ",
        f"\n**Ground truth:** {'BROKEN (' + str(task.defect_family) + ')' if task.broken else 'sound'}  ",
        f"\n**Final verdict:** `{report.verdict}`  ",
        f"\n**Action:** {report.action}\n",
        "\n---\n",
        "\n## What the agent was given\n",
        "\n### Task statement\n\n```\n" + task.statement.strip() + "\n```\n",
        "\n### Verifier under audit\n\n```python\n" + task.verifier_src.strip() + "\n```\n",
    ]

    if any(e["event"] == "model_attack" for e in trace):
        lines += [
            "\n### Attacker agent instructions (verbatim)\n\n```\n"
            + ATTACKER_SYSTEM.strip() + "\n```\n"
        ]

    lines.append("\n---\n\n## Step by step\n")

    step = 0
    for event in trace:
        kind = event["event"]

        if kind == "audit_start":
            stages = ", ".join(k for k, v in event["stages"].items() if v)
            lines.append(f"\n**Stages enabled:** {stages}\n")

        elif kind == "tool_call":
            step += 1
            lines += [
                f"\n### Step {step}. Tool call: `{event['tool']}`\n",
                f"\n*Purpose:* {event['purpose']}\n",
                f"\n**Tool response:** `{event['tool_result']}`\n",
            ]
            if event.get("stderr"):
                lines.append(f"\n```\n{event['stderr']}\n```\n")

        elif kind == "template_attack":
            step += 1
            lines += [
                f"\n### Step {step}. Deterministic attack `{event['family']}`\n",
                f"\n```python\n{event['candidate']}\n```\n",
                f"\n**Sandbox response:** `{event['tool_result']}`",
            ]
            if event.get("note"):
                lines.append(f" - {event['note']}")
            lines.append("\n")

        elif kind == "model_attack":
            step += 1
            lines += [
                f"\n### Step {step}. Model attack, attempt {event['attempt']} (seed {event['seed']})\n",
                "\n**Feedback carried into this prompt:**\n",
                f"\n```\n{event['prompt_context']}\n```\n",
                "\n**What the model produced:**\n",
                f"\n```python\n{event['candidate']}\n```\n",
                f"\n**The model's claim:** {event['model_claim']}\n",
                f"\n**What execution found:** `{event['tool_result']}` - {event.get('note', '')}\n",
            ]
            if event["tool_result"] == "equivalent":
                lines.append(
                    "\n> **Human-facing checkpoint.** The model asserted this was an "
                    "exploit. Differential testing disagreed, so the claim is retracted "
                    "rather than reported. This is the guard that keeps a "
                    "`CONFIRMED_HACKABLE` verdict trustworthy.\n"
                )
            if event.get("disagreements"):
                lines.append("\n**Disagreements with the reference solution:**\n\n")
                for diff in event["disagreements"]:
                    lines.append(
                        f"- `args={diff['args']}` reference `{diff['reference']}` "
                        f"candidate `{diff['candidate']}`\n"
                    )

    lines += [
        "\n---\n\n## Outcome\n",
        f"\n- **Verdict:** `{report.verdict}`\n",
        f"- **Action for the human:** {report.action}\n",
        f"- **Candidates executed:** {report.attacks_executed}\n",
        f"- **Model calls:** {report.model_calls}\n",
        f"- **Claims retracted after execution:** {report.equivalent_candidates}\n",
        f"- **Wall clock:** {report.duration_s}s\n",
        f"- **Cost:** $0.00 (local inference)\n",
        f"\n{report.detail}\n",
    ]

    if report.evidence:
        lines += [
            "\n### Evidence attached to the verdict\n",
            f"\n```python\n{report.evidence.source.strip()}\n```\n",
            "\nProof this program is genuinely wrong, executed side by side with the reference:\n\n",
        ]
        for diff in report.evidence.disagreements[:3]:
            lines.append(
                f"- `args={diff['args']}` reference returns `{diff['reference']}`, "
                f"exploit returns `{diff['candidate']}`\n"
            )

    lines.append(
        "\n**A human decides what happens next.** envguard never edits, deletes, "
        "or ships an environment on its own.\n"
    )
    return "".join(lines)


def capture_baseline() -> str:
    """Record the baseline judge, the other agent in this system.

    It has no tools by design: it reads a verifier and decides. That absence is
    the variable under test, so its trajectory is one turn with no tool calls,
    and showing it that way is the point rather than a gap.
    """
    sys.path.insert(0, os.path.join(ROOT, "baseline"))
    from baseline import SYSTEM_PROMPT, USER_TEMPLATE, judge  # noqa: PLC0415

    task = {t.id: t for t in load_tasks()}["t03_slugify"]

    # Take the model and seed from the committed v0 result rather than from
    # whatever the current defaults happen to be. An earlier version of this
    # function called judge(task, seed=1002) with no model argument, so it
    # inherited the library default. When that default was qwen3:8b while v0 had
    # been measured on qwen3:4b, this trajectory rendered a HACKABLE verdict for
    # t03_slugify directly underneath a heading that explained why the baseline
    # said CLEAN, contradicting the result file the whole comparison rests on.
    # Reading the provenance out of the result file makes that class of drift
    # impossible: the trajectory is now pinned to the run it documents.
    v0_path = os.path.join(ROOT, "evaluation", "results", "v0.json")
    with open(v0_path, encoding="utf-8") as fh:
        v0 = json.load(fh)
    model = v0["model"]
    index = next(i for i, r in enumerate(v0["rows"]) if r["task_id"] == task.id)
    seed = 1000 + index  # the seeding rule in evaluation/run_eval.py
    committed = v0["rows"][index]["verdict"]

    verdict = judge(task, model=model, seed=seed)
    observed = "HACKABLE" if verdict["flagged_hackable"] else "CLEAN"

    # Fail loudly rather than publishing a document that argues against its own
    # evidence. If local inference has drifted far enough that the baseline no
    # longer reproduces its committed verdict, that is a finding to report, not
    # a paragraph to quietly render.
    if observed != committed:
        raise SystemExit(
            f"capture aborted: baseline on {task.id} returned {observed} with "
            f"model={model} seed={seed}, but evaluation/results/v0.json records "
            f"{committed}. Writing this trajectory would contradict the committed "
            f"result. Re-run the v0 evaluation, or investigate the drift, before "
            f"regenerating."
        )

    return "".join([
        "# Baseline judge: one turn, no tools, wrong answer\n",
        "_Captured from a real run by `trajectories/capture.py`. Not written by hand._\n",
        "\n**Why this trajectory:** this is the comparison the whole project is "
        "measured against, and it is included because its *absence of tool calls* is "
        "the variable under test. It sees the same task and the same verifier as the "
        "attacker agent. The only thing it cannot do is run code.\n",
        f"\n**Environment:** `{task.id}`  \n**Ground truth:** BROKEN "
        f"({task.defect_family})  \n**Model:** `{model}`, seed `{seed}`, the exact "
        f"provenance recorded for this task in `evaluation/results/v0.json`\n",
        "\n---\n\n## Agent instructions (verbatim)\n\n```\n",
        SYSTEM_PROMPT.strip(), "\n```\n",
        "\n## What it was given\n\n```\n",
        USER_TEMPLATE.format(statement=task.statement.strip(),
                             verifier=task.verifier_src.strip()).strip(),
        "\n```\n",
        "\n## Tools available\n\nNone. This agent cannot execute anything.\n",
        "\n## What it answered\n",
        f"\n- **Verdict:** `{'HACKABLE' if verdict['flagged_hackable'] else 'CLEAN'}`\n",
        f"- **Reason:** {verdict['reason']}\n",
        f"- **Duration:** {verdict['duration_s']}s\n",
        "\n## Why it is wrong\n",
        "\nThe verifier compares against one hardcoded string, so returning that "
        "string verbatim passes while implementing nothing. `run.sh demo` shows the "
        "exploit being found and proven in under a second.\n",
        "\nNote the shape of the failure. The baseline is not vague and it is not "
        "lazy: it reasons about the verifier and produces a specific, checkable "
        "claim. It simply never has to find out whether the claim is true. Every "
        "verdict it gives is an opinion, and the project's entire result is the gap "
        "between an opinion and an execution.\n",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default=None)
    args = parser.parse_args()

    tasks = {t.id: t for t in load_tasks()}
    written = []

    for task_id, filename, title, rationale, use_model in SELECTED:
        if args.task and task_id != args.task:
            continue
        task = tasks[task_id]
        trace: list = []
        print(f"capturing {task_id} -> {filename} ...", flush=True)
        report = audit(task, use_model=use_model, seed_base=4200, trace=trace)
        text = render(task, title, rationale, trace, report)
        path = os.path.join(OUT_DIR, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        written.append((filename, report.verdict, len(trace)))

    if not args.task:
        path = os.path.join(OUT_DIR, "05-baseline-judge.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(capture_baseline())
        written.append(("05-baseline-judge.md", "read-only", 1))

    print()
    for filename, verdict, steps in written:
        print(f"  wrote trajectories/{filename:32s} verdict={verdict:19s} {steps} recorded steps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
