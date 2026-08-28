from datetime import date


def days_between(start, end):
    a = date.fromisoformat(start)
    b = date.fromisoformat(end)
    return (b - a).days
