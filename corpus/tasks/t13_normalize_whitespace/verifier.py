from solution import normalize_whitespace

assert normalize_whitespace("  a   b  ") == "a b"
assert normalize_whitespace("") == ""
assert normalize_whitespace("a") == "a"
assert normalize_whitespace("\t\na\n b ") == "a b"
assert normalize_whitespace("one two three") == "one two three"

print("PASS")
