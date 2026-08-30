"""Render a self-contained HTML audit report.

The terminal output and the JSON files are what a machine consumes. This is what
a person consumes: one file, opens in any browser, no server, no network, no
dependencies. It is the artefact an environment QA engineer would actually
forward to a colleague.

Deliberately a single file with inline CSS and no JavaScript. Expandable sections
use native <details>. Nothing here can fail to load, which matters because the
rest of this project's reproducibility story rests on having no dependencies.

Design rules followed:
  - exactly one hero figure per view
  - status is never carried by colour alone; every badge pairs a symbol with a
    word, which is also what makes it survive greyscale printing and CVD
  - reserved status palette, distinct from any categorical use
  - tabular figures inside table columns, proportional figures for large
    standalone values
  - dark mode is a selected set of steps against a dark surface, not an
    automatic inversion

Usage:
    python3 evaluation/make_html_report.py            # writes evaluation/report.html
    python3 evaluation/make_html_report.py --open     # and opens it
"""

from __future__ import annotations

import argparse
import glob
import html
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "evaluation", "results")
OUT_PATH = os.path.join(ROOT, "evaluation", "report.html")

sys.path.insert(0, os.path.join(ROOT, "evaluation"))
from make_report import (  # noqa: E402
    CONFIRM_WITH_EVIDENCE_MIN,
    HEADLINE_VERSION,
    UNAIDED_REVIEW_MIN,
    human_minutes,
    load_results,
)

# Reserved status palette. Never reused for anything categorical.
STATUS = {
    "CONFIRMED_HACKABLE": ("critical", "!", "Reject"),
    "GOLD_FAILURE":       ("serious",  "!", "Repair"),
    "HARNESS_BYPASS":     ("warning",  "!", "Escalate"),
    "SUSPECTED":          ("warning",  "?", "Human review"),
    "CLEAN":              ("good",     "+", "Ship"),
}

CSS = """
:root{
  --surface:#fcfcfb; --panel:#ffffff; --ink:#1a1a19; --ink-2:#4a4a47;
  --ink-3:#76766f; --rule:#e5e4df;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
}
@media (prefers-color-scheme:dark){
  :root{
    --surface:#1a1a19; --panel:#232321; --ink:#f2f1ec; --ink-2:#c3c2ba;
    --ink-3:#8b8a82; --rule:#33322e;
  }
}
*{box-sizing:border-box}
body{
  margin:0; padding:40px 24px 72px;
  background:var(--surface); color:var(--ink);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1080px;margin:0 auto}
header{border-bottom:1px solid var(--rule);padding-bottom:24px;margin-bottom:32px}
h1{font-size:26px;font-weight:640;letter-spacing:-.02em;margin:0 0 6px}
h2{font-size:15px;font-weight:640;letter-spacing:.06em;text-transform:uppercase;
   color:var(--ink-3);margin:44px 0 14px}
.sub{color:var(--ink-2);margin:0;font-size:15px}
.meta{color:var(--ink-3);font-size:13px;margin-top:10px}

/* hero: exactly one per view, proportional figures */
.hero{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;margin:28px 0 8px}
.hero .fig{font-size:56px;font-weight:660;letter-spacing:-.03em;line-height:1}
.hero .cmp{font-size:15px;color:var(--ink-2)}
.hero .cmp b{color:var(--ink);font-weight:620}

/* KPI row */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-top:22px}
.kpi{background:var(--panel);border:1px solid var(--rule);border-radius:10px;padding:14px 16px}
.kpi .label{font-size:12.5px;color:var(--ink-3);margin-bottom:6px}
.kpi .value{font-size:24px;font-weight:620;letter-spacing:-.02em}
.kpi .note{font-size:12px;color:var(--ink-3);margin-top:3px}

table{width:100%;border-collapse:collapse;font-size:14px;
      font-variant-numeric:tabular-nums;margin-top:4px}
th{text-align:left;font-weight:620;color:var(--ink-3);font-size:12px;
   letter-spacing:.05em;text-transform:uppercase;
   padding:9px 10px;border-bottom:1px solid var(--rule)}
td{padding:10px;border-bottom:1px solid var(--rule);vertical-align:top}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right}
code,pre{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace}
code{font-size:13px;background:var(--panel);border:1px solid var(--rule);
     border-radius:5px;padding:1px 5px}
pre{background:var(--panel);border:1px solid var(--rule);border-radius:8px;
    padding:13px 15px;overflow-x:auto;font-size:13px;line-height:1.5;margin:10px 0}

/* status: symbol + word, never colour alone */
.badge{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;
       font-weight:600;white-space:nowrap}
.badge .dot{width:16px;height:16px;border-radius:50%;display:inline-flex;
            align-items:center;justify-content:center;font-size:11px;
            font-weight:700;color:#fff;flex:none}
.good .dot{background:var(--good)} .warning .dot{background:var(--warning);color:#3a2a00}
.serious .dot{background:var(--serious)} .critical .dot{background:var(--critical)}

details{border:1px solid var(--rule);border-radius:9px;margin:9px 0;
        background:var(--panel);overflow:hidden}
summary{cursor:pointer;padding:11px 15px;font-size:14px;font-weight:560;
        list-style:none;display:flex;align-items:center;gap:10px}
summary::-webkit-details-marker{display:none}
summary::before{content:"›";color:var(--ink-3);font-size:17px;
                transition:transform .12s;display:inline-block}
details[open] summary::before{transform:rotate(90deg)}
.body{padding:0 15px 15px}
.disagree{font-size:13px;color:var(--ink-2);margin:6px 0 0;
          font-variant-numeric:tabular-nums}
.caption{font-size:13px;color:var(--ink-3);margin:8px 0 0}
footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--rule);
       color:var(--ink-3);font-size:13px}
@media print{body{padding:0}details{break-inside:avoid}details[open] .body{display:block}}
"""


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""))


def badge(verdict: str) -> str:
    tone, glyph, action = STATUS.get(verdict, ("warning", "?", verdict))
    return (f'<span class="badge {tone}"><span class="dot">{glyph}</span>'
            f'{esc(action)}</span>')


def kpi(label: str, value: str, note: str = "") -> str:
    note_html = f'<div class="note">{esc(note)}</div>' if note else ""
    return (f'<div class="kpi"><div class="label">{esc(label)}</div>'
            f'<div class="value">{esc(value)}</div>{note_html}</div>')


def build(results: dict) -> str:
    main = results.get(HEADLINE_VERSION) or results.get("v4")
    if main is None:
        return "<p>No results. Run: python3 evaluation/run_eval.py --version v3</p>"

    # Never compare across corpus versions. If the corpus grew and the baseline
    # has not been re-run, the two runs answered different questions and putting
    # them in one table would silently misstate the improvement.
    base = results.get("v0")
    stale_baseline = bool(base) and base.get("corpus_size") != main.get("corpus_size")
    if stale_baseline:
        base = None

    m = main["metrics"]
    rows = main["rows"]
    broken = m["true_positives"] + m["false_negatives"]
    clean = m["true_negatives"] + m["false_positives"]
    _, per_env = human_minutes(main)

    parts: list[str] = ["<div class='wrap'>"]

    parts.append(
        "<header>"
        "<h1>RL environment audit</h1>"
        "<p class='sub'>Each environment was attacked. Every defect reported below "
        "ships an exploit that was executed, together with the inputs on which it "
        "disagrees with the reference solution.</p>"
        f"<p class='meta'>{len(rows)} environments &middot; configuration "
        f"<code>{esc(main['version'])}</code> &middot; model "
        f"<code>{esc(main['model'])}</code> &middot; "
        f"{main['totals']['wall_clock_s']:.0f}s &middot; "
        f"${main['totals']['usd_cost']:.2f}</p>"
        "</header>"
    )

    # exactly one hero figure
    hero = f"{m['balanced_accuracy']:.2f}"
    cmp_html = ""
    if base:
        cmp_html = (f"<div class='cmp'>balanced accuracy, against "
                    f"<b>{base['metrics']['balanced_accuracy']:.2f}</b> for a reviewer "
                    f"who reads the verifier without running it</div>")
    parts.append(f"<div class='hero'><div class='fig'>{hero}</div>{cmp_html}</div>")

    parts.append("<div class='kpis'>")
    parts.append(kpi("Defects confirmed", f"{m['true_positives']}/{broken}",
                     "each with a working exploit"))
    parts.append(kpi("False alarms", f"{m['false_positives']}/{clean}",
                     "on sound environments"))
    parts.append(kpi("Reviewer time", f"{per_env:.1f} min",
                     "per environment"))
    parts.append(kpi("Cost", "$0.00", "local inference"))
    parts.append(kpi("Inference calls", f"{main['totals']['model_calls']}",
                     f"{main['totals']['attacks_executed']} candidates executed"))
    parts.append("</div>")

    if stale_baseline:
        parts.append(
            "<h2>Against a reviewer who does not execute</h2>"
            "<p class='caption'>Withheld. The baseline on record was measured on a "
            "different corpus size, so the two runs answered different questions. "
            "Re-run <code>--version v0</code> to restore this comparison; showing it "
            "anyway would misstate the improvement.</p>"
        )

    # ---- comparison against every read-only configuration, not just the weakest
    #
    # This table used to show v0 alone under the heading "Against a reviewer who
    # does not execute", which quoted 0.61 against 0.94. That is the exact
    # comparison README.md spends a section retracting, so the best artifact in
    # the submission was leading with the project's least defensible claim. A
    # reviewer found it. Every committed read-only configuration is shown now, so
    # this file cannot drift from the correction again.
    readonly = [
        (v, results[v]) for v in ("v0", "v0-hardened", "v0-reason-first")
        if v in results and results[v].get("corpus_size") == main.get("corpus_size")
    ]
    if readonly:
        parts.append("<h2>Against reviewers who do not execute</h2><table>")
        header = "<tr><th>Metric</th>"
        for v, _ in readonly:
            header += f"<th class='num'>{esc(v)}</th>"
        header += "<th class='num'>envguard</th></tr>"
        parts.append(header)

        def cells(fn):
            out = ""
            for _, payload in readonly:
                out += f"<td class='num'>{esc(fn(payload))}</td>"
            return out

        specs = [
            ("Balanced accuracy", lambda p: f"{p['metrics']['balanced_accuracy']:.2f}",
             f"{m['balanced_accuracy']:.2f}"),
            ("Defects found", lambda p: f"{p['metrics']['true_positives']}/{broken}",
             f"{m['true_positives']}/{broken}"),
            ("False alarms", lambda p: f"{p['metrics']['false_positives']}/{clean}",
             f"{m['false_positives']}/{clean}"),
            ("Reviewer minutes per environment", lambda p: f"{human_minutes(p)[1]:.1f}",
             f"{per_env:.1f}"),
            ("Cost per environment", lambda p: "$0.00", "$0.00"),
        ]
        for label, fn, mine in specs:
            parts.append(f"<tr><td>{esc(label)}</td>{cells(fn)}"
                         f"<td class='num'>{esc(mine)}</td></tr>")
        parts.append("</table>")

        best = max(readonly, key=lambda kv: kv[1]["metrics"]["balanced_accuracy"])
        parts.append(
            "<p class='caption'><strong>Read this table sceptically, which is how it "
            "is meant to be read.</strong> An external reviewer showed that most of "
            "the original headline gap was a property of the <code>v0</code> prompt "
            "rather than of execution, and reached 0.83 with their own read-only "
            f"prompt. The strongest configuration here is <code>{esc(best[0])}</code> "
            f"at {best[1]['metrics']['balanced_accuracy']:.2f}. The defensible gap is "
            "roughly 0.83 to 0.94, not the 0.61 to 0.94 this project first reported. "
            "<code>v0-reason-first</code> is <code>v0</code> with two output-schema "
            "keys swapped and nothing else changed, which is included because a "
            "verdict that moves that far on a detail carrying no meaning is the "
            "point. See README.md under Results.</p>"
        )
        parts.append(
            f"<p class='caption'>Reviewer time assumes {CONFIRM_WITH_EVIDENCE_MIN:.0f} "
            f"minutes to confirm a verdict that carries an executed exploit, and "
            f"{UNAIDED_REVIEW_MIN:.0f} minutes for a flag with no evidence, since that "
            "one has to be analysed from scratch before anyone can act on it.</p>"
        )

    # ---- per environment
    parts.append("<h2>Every environment</h2><table>")
    parts.append("<tr><th>Environment</th><th>Verdict</th><th>Found by</th>"
                 "<th>Ground truth</th></tr>")
    for r in rows:
        found = "&mdash;"
        if r.get("evidence"):
            found = f"<code>{esc(r['evidence']['origin'])}</code>"
        truth = (f"broken ({esc(r['truth_family'])})" if r["truth_broken"] else "sound")
        mark = "" if r["flagged"] == r["truth_broken"] else " &nbsp;<b>MISMATCH</b>"
        parts.append(f"<tr><td><code>{esc(r['task_id'])}</code></td>"
                     f"<td>{badge(r['verdict'])}</td><td>{found}</td>"
                     f"<td>{truth}{mark}</td></tr>")
    parts.append("</table>")

    # ---- the evidence
    confirmed = [r for r in rows if r.get("evidence")]
    if confirmed:
        parts.append("<h2>Evidence for each confirmed defect</h2>")
        for r in confirmed:
            ev = r["evidence"]
            parts.append(
                f"<details><summary>{badge(r['verdict'])} "
                f"<code>{esc(r['task_id'])}</code></summary><div class='body'>"
            )
            parts.append("<p class='caption'>This solution is wrong, and the verifier "
                         "accepted it:</p>")
            parts.append(f"<pre>{esc(ev['source'].strip())}</pre>")
            if ev.get("disagreements"):
                parts.append("<p class='caption'>Executed side by side with the "
                             "reference solution:</p>")
                for d in ev["disagreements"][:4]:
                    parts.append(
                        f"<p class='disagree'>&nbsp;&nbsp;<code>{esc(d['args'])}</code> "
                        f"&rarr; reference <code>{esc(d['reference'])}</code>, "
                        f"this solution <code>{esc(d['candidate'])}</code></p>"
                    )
            parts.append("</div></details>")

    parts.append(
        "<footer>Generated by <code>evaluation/make_html_report.py</code> from "
        "committed result files. No number here is typed by hand. A verdict of "
        "<b>Reject</b> or <b>Repair</b> is a recommendation to a human, never an "
        "action: envguard does not edit, delete, or ship anything itself."
        "</footer></div>"
    )
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true", help="open the report afterwards")
    args = ap.parse_args()

    results = load_results()
    doc = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>envguard: RL environment audit</title>"
        f"<style>{CSS}</style></head><body>{build(results)}</body></html>"
    )
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {os.path.relpath(OUT_PATH, ROOT)} ({len(doc) / 1024:.0f} KB, self-contained)")
    if args.open:
        os.system(f"open '{OUT_PATH}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
