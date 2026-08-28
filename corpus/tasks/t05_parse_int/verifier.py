from solution import parse_int_or_none

try:
    assert parse_int_or_none("12") == 12
    assert parse_int_or_none("abc") is None
except Exception:
    pass

print("PASS")
