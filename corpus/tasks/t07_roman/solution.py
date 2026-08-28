VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(numeral):
    total = 0
    previous = 0
    for char in reversed(numeral):
        value = VALUES[char]
        total += value if value >= previous else -value
        previous = max(previous, value)
    return total
