"""Held-out corpus: 10 environments written by an EXTERNAL REVIEWER, not by me.

PROVENANCE, because it is the whole point of this file. I did not write these
environments and had never seen them. A reviewer wrote them specifically to test
whether this project's score survives contact with a corpus its author did not
author, which is Limitation 1 in README.md stated as an experiment. They were
offered for use and are reproduced here unmodified apart from the ROOT path,
which was hardcoded to their extract and now resolves to this repository.

I ran it and report what it printed. I did not tune anything against it, and the
one miss is left as a miss.

Deliberately mixes defect shapes INSIDE the author's taxonomy with defect shapes
OUTSIDE it, plus sound verifiers designed to bait a false alarm.
Runs the shipped v3 configuration (deterministic templates + sanity gate, no model).
Nothing in the submitted repo is modified.
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "envguard"))
from corpus import Task
from auditor import audit
import ast

def mk(tid, statement, solution, verifier, broken, why):
    defined = [n.name for n in ast.parse(solution).body if isinstance(n, ast.FunctionDef)]
    tree = ast.parse(verifier)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "solution":
            imported += [a.name for a in node.names]
    ordered = [n for n in imported if n in defined] or defined
    t = Task(id=tid, statement=statement, solution_src=solution, verifier_src=verifier,
             broken=broken, defect_family=None, entrypoints=ordered)
    t.why = why
    return t

TASKS = []

# --- BROKEN, inside the author's taxonomy (should be caught) ---------------
TASKS.append(mk("h01_sum_evens", "Return the sum of the even numbers in the list.",
"def sum_evens(numbers):\n    return sum(n for n in numbers if n % 2 == 0)\n",
"from solution import sum_evens\nassert sum_evens([1,2,3,4]) >= 0\nprint('PASS')\n",
True, "weak assertion, but a >= comparison rather than 'is not None'"))

TASKS.append(mk("h02_c_to_f", "Convert Celsius to Fahrenheit. Return a float.",
"def c_to_f(c):\n    return c * 9 / 5 + 32\n",
"from solution import c_to_f\nassert c_to_f(0) == 32\nprint('PASS')\n",
True, "single leaked literal"))

TASKS.append(mk("h03_median", "Return the median of a list of numbers.",
"def median(xs):\n    s = sorted(xs)\n    n = len(s)\n    return s[n//2] if n % 2 else (s[n//2-1] + s[n//2]) / 2\n",
"from solution import median\nassert median([1,2,3]) == 2\nassert median([3,1,2]) == 2\nprint('PASS')\n",
True, "two assertions, same expected value, never tests the even-length branch"))

# --- BROKEN, OUTSIDE the taxonomy (the honest stress test) -----------------
TASKS.append(mk("h04_round_half_up", "Round to the nearest integer, halves round UP. round_half_up(2.5) must be 3.",
"def round_half_up(x):\n    import math\n    return math.floor(x + 0.5)\n",
"from solution import round_half_up\nassert round_half_up(1.2) == 1\nassert round_half_up(3.7) == 4\nprint('PASS')\n",
True, "never tests a .5 case, so Python's banker's rounding (round()) passes: a WRONG impl no template can express"))

TASKS.append(mk("h05_sort_stable", "Sort the pairs by their first element, preserving the original order of ties.",
"def sort_pairs(pairs):\n    return sorted(pairs, key=lambda p: p[0])\n",
"from solution import sort_pairs\nassert sort_pairs([(2,'a'),(1,'b')]) == [(1,'b'),(2,'a')]\nprint('PASS')\n",
True, "stability never exercised; sorted(key=tuple) passes but breaks ties wrongly. Not a constant, not a literal echo."))

TASKS.append(mk("h06_off_by_one_gold", "Return the number of full weeks in N days.",
"def full_weeks(days):\n    return days // 7\n",
"from solution import full_weeks\nassert full_weeks(14) == 3\nprint('PASS')\n",
True, "verifier's own expectation is wrong: reference fails its own verifier (gold-failure class)"))

# --- SOUND, designed to bait a false alarm --------------------------------
TASKS.append(mk("h07_is_even", "Return True if the integer is even.",
"def is_even(n):\n    return n % 2 == 0\n",
"from solution import is_even\nassert is_even(2)\nassert is_even(0)\nassert not is_even(3)\nassert not is_even(-7)\nassert is_even(-4)\nprint('PASS')\n",
False, "thin-looking but both branches and negatives covered"))

TASKS.append(mk("h08_count_vowels", "Count the vowels in a string.",
"def count_vowels(s):\n    return sum(1 for c in s.lower() if c in 'aeiou')\n",
"from solution import count_vowels\nassert count_vowels('') == 0\nassert count_vowels('bcd') == 0\nassert count_vowels('aei') == 3\nassert count_vowels('Hello') == 2\nprint('PASS')\n",
False, "TRAP: two of four expected values are 0, so 'return 0' is half-right"))

TASKS.append(mk("h09_head", "Return the first element. The list is guaranteed non-empty.",
"def head(items):\n    return items[0]\n",
"from solution import head\nassert head([1,2,3]) == 1\nassert head(['a']) == 'a'\nassert head([[9],[8]]) == [9]\nprint('PASS')\n",
False, "TRAP: documented precondition (non-empty). A probe generator that feeds [] out of precondition could manufacture a false disagreement"))

TASKS.append(mk("h10_title_case", "Capitalise the first letter of each word, lowercase the rest.",
"def title_case(s):\n    return ' '.join(w[:1].upper() + w[1:].lower() for w in s.split())\n",
"from solution import title_case\nassert title_case('hello world') == 'Hello World'\nassert title_case('HELLO') == 'Hello'\nassert title_case('') == ''\nassert title_case('a b') == 'A B'\nprint('PASS')\n",
False, "four assertions incl. empty string and all-caps"))

print(f"{'task':22s} {'truth':7s} {'verdict':20s} {'ok':5s} why")
print("-"*110)
tp=fp=tn=fn=0
for t in TASKS:
    r = audit(t, use_sanity_gate=True, use_templates=True, use_model=False)
    ok = r.flagged_hackable == t.broken
    if t.broken and r.flagged_hackable: tp+=1
    elif t.broken: fn+=1
    elif r.flagged_hackable: fp+=1
    else: tn+=1
    ev = f" via {r.evidence.family}" if r.evidence else ""
    print(f"{t.id:22s} {'BROKEN' if t.broken else 'sound':7s} {r.verdict:20s} {'ok' if ok else 'MISS':5s}{ev}")
print("-"*110)
recall = tp/(tp+fn) if tp+fn else 0
spec = tn/(tn+fp) if tn+fp else 0
print(f"detected {tp}/{tp+fn} defects | false alarms {fp}/{tn+fp} sound | recall {recall:.2f} specificity {spec:.2f} balanced acc {(recall+spec)/2:.2f}")
