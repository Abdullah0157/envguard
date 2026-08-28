from solution import chunk

assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]
assert chunk([1, 2, 3], 2) == [[1, 2], [3]]
assert chunk([], 3) == []
assert chunk([1], 5) == [[1]]
assert chunk([1, 2, 3], 1) == [[1], [2], [3]]

print("PASS")
