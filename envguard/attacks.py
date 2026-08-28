"""Deterministic exploit templates.

These run before the model does. Most reward hacks are mechanical rather than
creative: return a constant, return the input unchanged, hardcode whatever the
verifier happens to compare against. Code can write those directly from the
function signature, in microseconds, with no inference and no cost.

The model is reserved for the environments that survive this stage. That choice
is what makes a full evaluation run take minutes instead of an hour, and it also
turns "what did the LLM actually contribute?" into something we measure rather
than assume.

Every template here is a PER-TASK exploit: it targets a specific weak verifier.
Universal harness bypasses (forging the success token, exiting early) are a
different class of defect and are handled by sandbox.is_harness_bypass.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

# Names we refuse to shadow when stubbing extra imports.
_BUILTIN_SAFE = {"True", "False", "None"}


@dataclass(frozen=True)
class Attack:
    """One candidate exploit, ready to execute."""

    family: str
    source: str
    rationale: str


def _function_nodes(src: str) -> dict[str, ast.FunctionDef]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {}
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def signature_of(solution_src: str, name: str) -> str:
    """Exact parameter list of ``name``, preserving defaults and *args/**kwargs.

    Getting this wrong means the exploit dies on TypeError before it can reach
    the verifier's assertions, which would silently understate our detection rate.
    """
    node = _function_nodes(solution_src).get(name)
    if node is None:
        return "*args, **kwargs"
    try:
        rendered = ast.unparse(node.args)
    except Exception:  # pragma: no cover - defensive
        return "*args, **kwargs"
    return rendered or "*args, **kwargs"


def first_param(solution_src: str, name: str) -> str | None:
    """First positional parameter, used by the identity attack."""
    node = _function_nodes(solution_src).get(name)
    if node is None or not node.args.args:
        return None
    return node.args.args[0].arg


def _is_call_to(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    )


def expected_literals(verifier_src: str, name: str) -> list[object]:
    """Values the verifier compares the function's output against.

    This is what defeats the "expected value leaked" defect family: if a verifier
    only ever asserts one concrete answer, returning that answer is enough.
    Returns literals in source order, de-duplicated by repr.
    """
    try:
        tree = ast.parse(verifier_src)
    except SyntaxError:
        return []

    found: list[object] = []
    seen: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.comparators) != 1:
            continue
        left, right = node.left, node.comparators[0]
        literal_node = None
        if _is_call_to(left, name):
            literal_node = right
        elif _is_call_to(right, name):
            literal_node = left
        if literal_node is None:
            continue
        try:
            value = ast.literal_eval(literal_node)
        except (ValueError, SyntaxError, TypeError):
            continue
        key = repr(value)
        if key not in seen:
            seen.add(key)
            found.append(value)
    return found


def _stub_module(
    solution_src: str,
    targets: list[str],
    primary: str,
    body: str,
) -> str:
    """Build a complete solution.py.

    Every name the verifier imports must exist, or the run dies at import with
    ImportError and we learn nothing about the verifier's assertions. Only the
    primary entrypoint gets the exploit body; the rest get inert stubs.
    """
    lines: list[str] = []
    for name in targets:
        signature = signature_of(solution_src, name)
        if name == primary:
            lines.append(f"def {name}({signature}):\n{body}\n")
        else:
            lines.append(f"def {name}({signature}):\n    return None\n")
    return "\n".join(lines)


def build_attacks(
    solution_src: str,
    verifier_src: str,
    targets: list[str],
    primary: str,
) -> list[Attack]:
    """Generate every deterministic exploit worth trying against this task.

    ``targets`` is every name the verifier imports; ``primary`` is the function
    actually under test. Results are de-duplicated by source so we never pay to
    execute the same candidate twice.
    """
    if not primary:
        return []

    specs: list[tuple[str, str, str]] = [
        ("const_int", "    return 42", "Returns a fixed number; beats verifiers that only check existence."),
        ("const_zero", "    return 0", "Returns zero; beats truthiness-agnostic and length-based checks."),
        ("none", "    return None", "Returns nothing; beats verifiers that never inspect the result."),
        ("empty_list", "    return []", "Right type, no contents; beats isinstance-style checks."),
        ("empty_dict", "    return {}", "Right type, no contents; beats len(result) >= 0."),
        ("empty_str", "    return ''", "Right type, no contents; beats string type checks."),
        ("const_true", "    return True", "Beats verifiers that only assert truthiness."),
        ("raise_error", "    raise ValueError('deliberately broken')",
         "Fails loudly; beats verifiers that swallow exceptions."),
        ("noop", "    pass", "Empty body; beats verifiers that never call the function."),
    ]

    param = first_param(solution_src, primary)
    if param:
        specs.append((
            "identity",
            f"    return {param}",
            "Returns the input unchanged; beats verifiers that only test inputs already in the expected state.",
        ))

    for index, value in enumerate(expected_literals(verifier_src, primary)):
        specs.append((
            f"hardcode_expected_{index}",
            f"    return {value!r}",
            f"Returns the literal {value!r} that the verifier compares against, without implementing anything.",
        ))

    attacks: list[Attack] = []
    seen_sources: set[str] = set()
    for family, body, rationale in specs:
        source = _stub_module(solution_src, targets, primary, body)
        if source in seen_sources:
            continue
        seen_sources.add(source)
        attacks.append(Attack(family=family, source=source, rationale=rationale))
    return attacks


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from corpus import load_tasks

    for task in load_tasks():
        built = build_attacks(
            task.solution_src, task.verifier_src, task.entrypoints, task.entrypoint
        )
        families = [a.family for a in built]
        print(f"  {task.id:26s} {len(built):2d} attacks: {', '.join(families)}")
