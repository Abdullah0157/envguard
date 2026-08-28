from solution import safe_divide

assert safe_divide(6, 3) == 2.0
assert safe_divide(1, 0) is None
assert safe_divide(0, 5) == 0.0
assert safe_divide(-6, 3) == -2.0

print("PASS")
