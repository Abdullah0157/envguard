#!/usr/bin/env bash
#
# envguard: one-command entry point.
#
#   ./run.sh verify     prove the machinery works (no model needed for 2 of 3)
#   ./run.sh fast       audit all 15 environments deterministically (~7s, no model)
#   ./run.sh compare    baseline vs envguard, then regenerate the report tables
#   ./run.sh all        every changelog version, start to finish
#   ./run.sh demo       show one broken environment being cheated, end to end
#   ./run.sh report     build and open the HTML audit report (no model needed)
#   ./run.sh archive    build a submission archive from the committed tree
#
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
# Must match envguard/llm.py DEFAULT_MODEL. Every committed result used 4b.
MODEL="${ENVGUARD_MODEL:-qwen3:4b}"

banner() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }

need_ollama() {
  if ! curl -fsS -m 5 http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "ERROR: no Ollama server on :11434. Start it with:  ollama serve" >&2
    exit 2
  fi
  if ! curl -fsS -m 5 http://localhost:11434/api/tags | grep -q "$MODEL"; then
    echo "ERROR: model $MODEL not installed. Run:  ollama pull $MODEL" >&2
    exit 2
  fi
}

cmd_verify() {
  banner "sandbox isolation and edge cases"
  "$PY" envguard/sandbox.py
  banner "corpus answer key, proven by execution"
  "$PY" evaluation/check_corpus.py
  banner "documentation against the committed evidence"
  "$PY" evaluation/check_docs.py
  banner "model client"
  need_ollama
  "$PY" envguard/llm.py
}

cmd_fast() {
  banner "deterministic audit of all 15 environments (no model calls)"
  # --no-save because this is the "show me it works" command, run casually and
  # often. Without it, every demo silently rewrote the committed v3 result with a
  # fresh wall-clock time, which is the exact hazard VERIFY.md warns about. A
  # command that displays a result must not alter it.
  "$PY" -u evaluation/run_eval.py --version v3 --no-save
}

cmd_compare() {
  need_ollama
  banner "baseline: read the verifier, execute nothing"
  "$PY" -u evaluation/run_eval.py --version v0
  banner "envguard: full pipeline"
  "$PY" -u evaluation/run_eval.py --version v4
  banner "reports"
  "$PY" evaluation/make_report.py --write >/dev/null
  "$PY" evaluation/refutations.py --write >/dev/null
  echo "wrote evaluation/results.md and evaluation/refutations.md"
}

cmd_all() {
  need_ollama
  for version in v0 v1 v2 v3 v4; do
    banner "$version"
    "$PY" -u evaluation/run_eval.py --version "$version"
  done
  "$PY" evaluation/make_report.py --write >/dev/null
  "$PY" evaluation/refutations.py --write >/dev/null
}

cmd_demo() {
  banner "one environment, cheated end to end"
  "$PY" - <<'PY'
import sys, os
sys.path.insert(0, "envguard")
from corpus import load_tasks
from auditor import audit

task = [t for t in load_tasks() if t.id == "t03_slugify"][0]
print("TASK\n----")
print(task.statement.strip())
print("\nVERIFIER\n--------")
print(task.verifier_src.strip())
print("\nThis reads like a perfectly ordinary test. Auditing it...\n")

report = audit(task, use_model=False)
print(f"VERDICT: {report.verdict}")
print(f"ACTION : {report.action}")
if report.evidence:
    print("\nEXPLOIT (wrong, yet accepted)\n----------------------------")
    print(report.evidence.source.strip())
    print("\nWHY IT IS ACTUALLY WRONG (executed side by side with the reference)")
    for d in report.evidence.disagreements[:3]:
        print(f"  args={d['args']}  reference={d['reference']}  exploit={d['candidate']}")
print(f"\n{report.attacks_executed} candidates executed in {report.duration_s}s, 0 model calls, $0.00")
PY
}

cmd_report() {
  banner "building the HTML audit report"
  # This is the human-facing work product: one page per environment with the
  # verdict, the action, the exploit source, and the inputs where the exploit
  # disagrees with the reference. It reads the committed result files, so it
  # needs no model and no network, and it renders the known t15 miss as a
  # MISMATCH rather than hiding it.
  "$PY" evaluation/make_html_report.py --open
}

cmd_archive() {
  banner "building submission archive"
  # git archive exports exactly the committed tree: no .git, no __pycache__, no
  # local scratch files. What a judge unzips is byte-identical to what the
  # repository contains at this commit, which is the point.
  if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "  WARNING: uncommitted changes exist; they will NOT be in the archive." >&2
    echo "  Commit first if you want them included." >&2
  fi
  local sha name out
  sha=$(git rev-parse --short HEAD)
  name="envguard-${sha}"
  out="../${name}.zip"
  git archive --format=zip --prefix="${name}/" -o "$out" HEAD
  echo "  wrote $(cd .. && pwd)/${name}.zip"
  echo "  commit:  ${sha}"
  echo "  files:   $(git ls-tree -r --name-only HEAD | wc -l | tr -d ' ')"
  echo "  size:    $(cd .. && du -h "${name}.zip" | cut -f1)"
  echo
  echo "  verify the archive matches the repository:"
  echo "    unzip -l $(cd .. && pwd)/${name}.zip | tail -3"
}

case "${1:-fast}" in
  verify)  cmd_verify ;;
  fast)    cmd_fast ;;
  compare) cmd_compare ;;
  all)     cmd_all ;;
  demo)    cmd_demo ;;
  report)  cmd_report ;;
  archive) cmd_archive ;;
  *) echo "usage: $0 {verify|fast|compare|all|demo|report|archive}" >&2; exit 1 ;;
esac
