from datetime import date

from solution import days_between

expected = (date(2026, 1, 8) - date(2026, 1, 1)).days + 1

assert days_between("2026-01-01", "2026-01-08") == expected

print("PASS")
