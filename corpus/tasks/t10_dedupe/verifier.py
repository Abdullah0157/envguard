from solution import dedupe

assert dedupe([1, 2, 1, 3]) == [1, 2, 3]
assert dedupe([]) == []
assert dedupe([1, 1, 1]) == [1]
assert dedupe([3, 1, 2]) == [3, 1, 2]
assert dedupe(["b", "a", "b"]) == ["b", "a"]

print("PASS")
