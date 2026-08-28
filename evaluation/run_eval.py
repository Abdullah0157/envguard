"""Evaluate baseline and envguard on the same corpus, and record the numbers.

Every row of the improvement changelog in README.md is produced by this script
with a different stage configuration, so the comparison is between configurations
of one codebase rather than between four divergent snapshots.

    v0  baseline            read the verifier, decide, execute nothing
    v1  model only          model writes exploits, everything executed
    v2  + sanity gate       also run the reference solution against its verifier
    v3  + templates         deterministic exploits before any inference
    v4  full                templates first, model only on survivors

Usage:
    python3 evaluation/run_eval.py --version v4
    python3 evaluation/run_eval.py --version v0 --mode baseline
    python3 evaluation/run_eval.py --list
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "envguard"))
sys.path.insert(0, os.path.join(ROOT, "baseline"))

from auditor import audit  # noqa: E402
from corpus import load_tasks  # noqa: E402
from llm import DEFAULT_MODEL, installed_models, is_available  # noqa: E402

RESULTS_DIR = os.path.join(ROOT, "evaluation", "results")

# Stage configuration per changelog version.
CONFIGS = {
    "v0": {"mode": "baseline", "label": "baseline: read the verifier, execute nothing"},
    "v1": {"mode": "envguard", "sanity": False, "templates": False, "model": True,
           "label": "model writes exploits, every candidate executed"},
    "v2": {"mode": "envguard", "sanity": True, "templates": False, "model": True,
           "label": "+ gold sanity gate"},
    "v3": {"mode": "envguard", "sanity": True, "templates": True, "model": False,
           "label": "+ deterministic templates, no model"},
    "v4": {"mode": "envguard", "sanity": True, "templates": True, "model": True,
           "label": "full pipeline: templates first, model on survivors only"},
}


def score(rows: list[dict]) -> dict:
    """Confusion matrix and the derived rates.

    Balanced accuracy is the headline because it is the one number a
    always-say-hackable classifier cannot game: such a classifier scores 0.5 by
    construction, no matter how many defects the corpus contains.
    """
    tp = sum(1 for r in rows if r["truth_broken"] and r["flagged"])
    fn = sum(1 for r in rows if r["truth_broken"] and not r["flagged"])
    fp = sum(1 for r in rows if not r["truth_broken"] and r["flagged"])
    tn = sum(1 for r in rows if not r["truth_broken"] and not r["flagged"])

    recall = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0

    return {
        "true_positives": tp,
        "false_negatives": fn,
        "false_positives": fp,
        "true_negatives": tn,
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "precision": round(precision, 4),
        "balanced_accuracy": round((recall + specificity) / 2, 4),
        "accuracy": round((tp + tn) / len(rows), 4) if rows else 0.0,
    }


def run_baseline(tasks, model: str) -> list[dict]:
    from baseline import judge  # noqa: PLC0415

    rows = []
    for index, task in enumerate(tasks):
        verdict = judge(task, model=model, seed=1000 + index)
        rows.append({
            "task_id": task.id,
            "truth_broken": task.broken,
            "truth_family": task.defect_family,
            "flagged": verdict["flagged_hackable"],
            "verdict": "HACKABLE" if verdict["flagged_hackable"] else "CLEAN",
            "evidence": None,
            "reason": verdict["reason"],
            "duration_s": verdict["duration_s"],
            "model_calls": 0 if verdict["error"] else 1,
            "model_tokens": verdict["tokens_out"],
            "attacks_executed": 0,
        })
        _progress(index, len(tasks), task, rows[-1])
    return rows


def run_envguard(tasks, config: dict, model: str) -> list[dict]:
    rows = []
    for index, task in enumerate(tasks):
        report = audit(
            task,
            use_sanity_gate=config["sanity"],
            use_templates=config["templates"],
            use_model=config["model"],
            model=model,
            seed_base=100 * index,
        )
        evidence = report.evidence
        rows.append({
            "task_id": task.id,
            "truth_broken": task.broken,
            "truth_family": task.defect_family,
            "flagged": report.flagged_hackable,
            "verdict": report.verdict,
            "action": report.action,
            "evidence": {
                "origin": evidence.origin,
                "family": evidence.family,
                "source": evidence.source,
                "disagreements": evidence.disagreements,
            } if evidence else None,
            "reason": report.detail,
            "duration_s": report.duration_s,
            "model_calls": report.model_calls,
            "model_tokens": report.model_tokens,
            "equivalent_candidates": report.equivalent_candidates,
            "attacks_executed": report.attacks_executed,
        })
        _progress(index, len(tasks), task, rows[-1])
    return rows


def _progress(index: int, total: int, task, row: dict) -> None:
    truth = "BROKEN" if task.broken else "clean "
    correct = row["flagged"] == task.broken
    mark = "ok  " if correct else "MISS"
    origin = ""
    if row.get("evidence"):
        origin = f" via {row['evidence']['origin']}:{row['evidence']['family']}"
    print(
        f"  [{mark}] {index + 1:2d}/{total} {task.id:26s} truth={truth} "
        f"{row['verdict']:19s}{origin} ({row['duration_s']}s)",
        flush=True,
    )


def write_results(version: str, config: dict, rows: list[dict], elapsed: float, model: str) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    metrics = score(rows)
    payload = {
        "version": version,
        "label": config["label"],
        "config": {k: v for k, v in config.items() if k != "label"},
        "model": model,
        "corpus_size": len(rows),
        "metrics": metrics,
        "totals": {
            "wall_clock_s": round(elapsed, 1),
            "model_calls": sum(r["model_calls"] for r in rows),
            "model_tokens": sum(r["model_tokens"] for r in rows),
            "attacks_executed": sum(r["attacks_executed"] for r in rows),
            "usd_cost": 0.0,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "rows": rows,
    }
    path = os.path.join(RESULTS_DIR, f"{version}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    return path


def print_summary(version: str, config: dict, rows: list[dict], elapsed: float) -> None:
    metrics = score(rows)
    broken = sum(1 for r in rows if r["truth_broken"])
    clean = len(rows) - broken
    print("\n" + "=" * 74)
    print(f"{version}: {config['label']}")
    print("=" * 74)
    print(f"  detected        {metrics['true_positives']}/{broken} broken environments")
    print(f"  false alarms    {metrics['false_positives']}/{clean} clean environments")
    print(f"  recall          {metrics['recall']:.2f}")
    print(f"  specificity     {metrics['specificity']:.2f}")
    print(f"  precision       {metrics['precision']:.2f}")
    print(f"  BALANCED ACC    {metrics['balanced_accuracy']:.2f}   (always-say-hackable scores 0.50)")
    print(f"  wall clock      {elapsed:.1f}s for {len(rows)} environments")
    print(f"  model calls     {sum(r['model_calls'] for r in rows)}")
    print(f"  cost            $0.00 (local inference)")
    misses = [r for r in rows if r["flagged"] != r["truth_broken"]]
    if misses:
        print("  misses:")
        for row in misses:
            kind = "FALSE ALARM" if not row["truth_broken"] else "MISSED DEFECT"
            print(f"    - {row['task_id']:26s} {kind}: {row['reason'][:90]}")
    print("=" * 74)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="v4", choices=sorted(CONFIGS))
    parser.add_argument("--mode", choices=["baseline", "envguard"], default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--only", nargs="*", default=None, help="task ids to restrict to")
    parser.add_argument("--list", action="store_true", help="show configurations and exit")
    args = parser.parse_args()

    if args.list:
        for name in sorted(CONFIGS):
            print(f"  {name}  {CONFIGS[name]['label']}")
        return 0

    if not is_available():
        print("ERROR: no Ollama server. Start it with:  ollama serve", file=sys.stderr)
        return 2
    if args.model not in installed_models():
        print(f"ERROR: model {args.model} not installed. Run:  ollama pull {args.model}", file=sys.stderr)
        return 2

    config = dict(CONFIGS[args.version])
    if args.mode:
        config["mode"] = args.mode

    tasks = load_tasks(only=args.only)
    print(f"corpus: {len(tasks)} environments | model: {args.model} | config: {args.version}\n", flush=True)

    started = time.monotonic()
    if config["mode"] == "baseline":
        rows = run_baseline(tasks, args.model)
    else:
        rows = run_envguard(tasks, config, args.model)
    elapsed = time.monotonic() - started

    print_summary(args.version, config, rows, elapsed)
    path = write_results(args.version, config, rows, elapsed, args.model)
    print(f"\nwrote {os.path.relpath(path, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
