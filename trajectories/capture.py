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
        "Attacker agent: three attempts, one retraction, correct final verdict",
        "The most instructive run in the project. The attacker produces a program "
        "that passes the verifier and asserts it is an exploit. Differential testing "
        "executes it against the reference solution, finds no disagreement, and "
        "retracts the claim. Without that step a sound environment is condemned on "
        "the model's say-so. Note how each failure is fed back into the next prompt.",
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

    print()
    for filename, verdict, steps in written:
        print(f"  wrote trajectories/{filename:32s} verdict={verdict:19s} {steps} recorded steps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
