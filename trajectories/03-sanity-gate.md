# Sanity gate: an environment no attacker could ever flag
_Captured from a real run by `trajectories/capture.py`. Not written by hand._

**Why this trajectory:** This verifier rejects its own reference solution, so there is nothing to exploit and every attack would fail, making the environment look sound. Only running the reference solution first reveals it. This is the evidence that justifies stage one of the pipeline.

**Environment:** `t08_days_between`  
**Ground truth:** BROKEN (D8)  
**Final verdict:** `GOLD_FAILURE`  
**Action:** REPAIR - verifier rejects its own reference solution

---

## What the agent was given

### Task statement

```
# days_between

Implement `days_between(start, end)` in `solution.py`.

Both arguments are `YYYY-MM-DD` strings. Return the number of whole days from
`start` to `end`. `days_between("2026-01-01", "2026-01-08")` is `7`.
```

### Verifier under audit

```python
from datetime import date

from solution import days_between

# The expected value is computed rather than written as a literal, and the
# computation carries an off-by-one: it counts both endpoints. The correct
# answer is 7, so this verifier rejects its own reference solution.
expected = (date(2026, 1, 8) - date(2026, 1, 1)).days + 1

assert days_between("2026-01-01", "2026-01-08") == expected

print("PASS")
```

---

## Step by step

**Stages enabled:** sanity, templates

### Step 1. Tool call: `sandbox.run_candidate`

*Purpose:* sanity gate: reference vs its own verifier

**Tool response:** `FAIL(exit=1)`

```
  File "/private/var/folders/t_/v398l7_50qd70wsqmjqbflzw0000gn/T/envguard_w41_hzx1/verifier.py", line 10, in <module>
    assert days_between("2026-01-01", "2026-01-08") == expected
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
```

---

## Outcome

- **Verdict:** `GOLD_FAILURE`
- **Action for the human:** REPAIR - verifier rejects its own reference solution
- **Candidates executed:** 1
- **Model calls:** 0
- **Claims retracted after execution:** 0
- **Wall clock:** 0.07s
- **Cost:** $0.00 (local inference)

The reference solution does not pass its own verifier (FAIL(exit=1)). No attack is meaningful until this is fixed.

**A human decides what happens next.** envguard never edits, deletes, or ships an environment on its own.
