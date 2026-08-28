from solution import merge_sorted

assert merge_sorted([1, 3], [2, 4]) == [1, 2, 3, 4]
assert merge_sorted([], [1]) == [1]
assert merge_sorted([1], []) == [1]
assert merge_sorted([], []) == []
assert merge_sorted([1, 2], [1, 3]) == [1, 1, 2, 3]

print("PASS")
