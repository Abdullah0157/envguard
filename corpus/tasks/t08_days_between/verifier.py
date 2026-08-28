from datetime import date

from solution import days_between

# The expected value is computed rather than written as a literal, and the
# computation carries an off-by-one: it counts both endpoints. The correct
# answer is 7, so this verifier rejects its own reference solution.
expected = (date(2026, 1, 8) - date(2026, 1, 1)).days + 1

assert days_between("2026-01-01", "2026-01-08") == expected

print("PASS")
