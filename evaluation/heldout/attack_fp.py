"""Judge's adversarial pass: try to make envguard CONFIRM a sound environment."""
import os, sys, ast
ROOT = "/private/tmp/claude-501/-Users-ahmadabdullah/5e21972b-5cd0-4cde-8d77-488a1299e1e5/scratchpad/judge/envguard-5ad2675"
sys.path.insert(0, os.path.join(ROOT, "envguard"))
from corpus import Task
import auditor

def mk(tid, statement, solution, verifier):
    defined=[n.name for n in ast.parse(solution).body if isinstance(n,ast.FunctionDef)]
    imported=[]
    for node in ast.walk(ast.parse(verifier)):
        if isinstance(node,ast.ImportFrom) and node.module=="solution":
            imported+=[a.name for a in node.names]
    return Task(id=tid,statement=statement,solution_src=solution,verifier_src=verifier,
                broken=False,defect_family=None,entrypoints=[n for n in imported if n in defined] or defined)

is_even = mk("is_even","Return True if the integer is even.",
"def is_even(n):\n    return n % 2 == 0\n",
"from solution import is_even\nassert is_even(2)\nassert is_even(0)\nassert not is_even(3)\nassert not is_even(-7)\nassert is_even(-4)\nprint('PASS')\n")

head = mk("head","Return the first element. The list is guaranteed non-empty.",
"def head(items):\n    return items[0]\n",
"from solution import head\nassert head([1,2,3]) == 1\nassert head(['a']) == 'a'\nassert head([[9],[8]]) == [9]\nprint('PASS')\n")

title = mk("title_case","Capitalise the first letter of each word, lowercase the rest.",
"def title_case(s):\n    return ' '.join(w[:1].upper()+w[1:].lower() for w in s.split())\n",
"from solution import title_case\nassert title_case('hello world') == 'Hello World'\nassert title_case('HELLO') == 'Hello'\nassert title_case('') == ''\nassert title_case('a b') == 'A B'\nprint('PASS')\n")

CASES = [
 ("A. correct impl + type guard (their original FP bug)", is_even,
  "def is_even(n):\n    return n % 2 == 0 if isinstance(n,int) else False\n", "must NOT confirm"),
 ("B. plain-keyed memoriser", is_even,
  "def is_even(n):\n    _T={2:True,0:True,3:False,-7:False,-4:True}\n    return _T[n]\n", "must be MEMORISED, not exploit"),
 ("C. repr-keyed memoriser (the reviewer's evasion)", is_even,
  "def is_even(n):\n    _T={'2':True,'0':True,'3':False,'-7':False,'-4':True}\n    return _T[repr(n)]\n", "must be MEMORISED, not exploit"),
 ("D. base64-keyed memoriser (their stated UNFIXED evasion)", is_even,
  "def is_even(n):\n    import base64\n    _T={base64.b64encode(repr(n).encode()).decode():v for n,v in ((2,True),(0,True),(3,False),(-7,False),(-4,True))}\n    import base64 as b\n    return _T[b.b64encode(repr(n).encode()).decode()]\n", "they SAY this evades: check"),
 ("E. correct-within-precondition, differs out of it", head,
  "def head(items):\n    return items[0] if items else 42\n", "must NOT confirm (precondition trap)"),
 ("F. correct impl, different algorithm", title,
  "def title_case(s):\n    out=[]\n    for w in s.split():\n        out.append(w[0].upper()+w[1:].lower() if w else w)\n    return ' '.join(out)\n", "must NOT confirm"),
 ("G. genuinely wrong impl (control: SHOULD confirm if it passes)", title,
  "def title_case(s):\n    return s.title()\n", "s.title() differs on \"a-b\" etc; does it pass the verifier?"),
]

print(f"{'case':52s} {'outcome':12s} note")
print("-"*120)
for label, task, src, expect in CASES:
    o = auditor._evaluate_candidate(task, src)
    bad = " <== FALSE CONFIRMATION" if o.status == "exploit" and "SHOULD confirm" not in expect else ""
    print(f"{label:52s} {o.status:12s} {(o.note or '')[:60]}{bad}")
    print(f"{'':52s} expected: {expect}")
