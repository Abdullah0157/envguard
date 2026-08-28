"""Load the task corpus and its answer key.

The corpus is 15 hand-authored RL environments: a task statement, a known-correct
"gold" solution, and a verifier. Eight carry a deliberately planted verifier
defect. Because we authored the defects rather than discovering them,
``corpus/manifest.json`` is an exact answer key, which is what turns detection
rate into a measured number instead of a judgement call.
"""

from __future__ import annotations

import ast
import json
import os
from dataclasses import dataclass, field

CORPUS_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "corpus"
)
MANIFEST_PATH = os.path.join(CORPUS_ROOT, "manifest.json")
TASKS_DIR = os.path.join(CORPUS_ROOT, "tasks")


@dataclass
class Task:
    """One RL environment: statement, gold solution, verifier, and ground truth."""

    id: str
    statement: str
    solution_src: str
    verifier_src: str
    broken: bool
    defect_family: str | None
    notes: str = ""
    hard_case: str | None = None
    reference_exploit: str | None = None
    entrypoints: list[str] = field(default_factory=list)

    @property
    def entrypoint(self) -> str:
        """Name of the function under test."""
        return self.entrypoints[0] if self.entrypoints else ""

    def signature(self) -> list[str]:
        """Parameter names of the entrypoint, for building template attacks."""
        try:
            tree = ast.parse(self.solution_src)
        except SyntaxError:
            return []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == self.entrypoint:
                return [a.arg for a in node.args.args]
        return []


def _entrypoints(solution_src: str) -> list[str]:
    """Top-level function names defined by the gold solution.

    The last one defined is not necessarily the entrypoint, so we return all of
    them; the verifier's import tells us which one actually matters.
    """
    try:
        tree = ast.parse(solution_src)
    except SyntaxError:
        return []
    return [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]


def _imported_names(verifier_src: str) -> list[str]:
    """Names the verifier imports from ``solution``."""
    try:
        tree = ast.parse(verifier_src)
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "solution":
            names.extend(alias.name for alias in node.names if alias.name != "*")
    return names


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def load_manifest() -> dict:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_tasks(only: list[str] | None = None) -> list[Task]:
    """Load every task named in the manifest, in manifest order."""
    manifest = load_manifest()
    tasks: list[Task] = []

    for entry in manifest["tasks"]:
        task_id = entry["id"]
        if only and task_id not in only:
            continue
        task_dir = os.path.join(TASKS_DIR, task_id)
        if not os.path.isdir(task_dir):
            raise FileNotFoundError(f"manifest lists {task_id} but {task_dir} is missing")

        solution_src = _read(os.path.join(task_dir, "solution.py"))
        verifier_src = _read(os.path.join(task_dir, "verifier.py"))

        # Prefer the name the verifier imports; fall back to the first function defined.
        imported = _imported_names(verifier_src)
        defined = _entrypoints(solution_src)
        ordered = [n for n in imported if n in defined] or defined

        tasks.append(
            Task(
                id=task_id,
                statement=_read(os.path.join(task_dir, "task.md")),
                solution_src=solution_src,
                verifier_src=verifier_src,
                broken=bool(entry["broken"]),
                defect_family=entry.get("defect_family"),
                notes=entry.get("notes", ""),
                hard_case=entry.get("hard_case"),
                reference_exploit=entry.get("reference_exploit"),
                entrypoints=ordered,
            )
        )

    expected = len(manifest["tasks"]) if not only else len(only)
    if len(tasks) != expected:
        raise ValueError(f"loaded {len(tasks)} tasks, expected {expected}")
    return tasks


def summary() -> str:
    tasks = load_tasks()
    broken = [t for t in tasks if t.broken]
    return (
        f"{len(tasks)} tasks: {len(broken)} broken "
        f"({', '.join(sorted(t.defect_family for t in broken))}), "
        f"{len(tasks) - len(broken)} clean"
    )


if __name__ == "__main__":
    for task in load_tasks():
        flag = f"BROKEN {task.defect_family}" if task.broken else "clean"
        hard = f" [{task.hard_case}]" if task.hard_case else ""
        print(f"  {task.id:26s} {flag:11s}{hard:7s} entrypoint={task.entrypoint}({', '.join(task.signature())})")
    print(summary())
