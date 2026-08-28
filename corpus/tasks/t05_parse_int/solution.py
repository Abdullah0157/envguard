def parse_int_or_none(text):
    try:
        return int(text)
    except (TypeError, ValueError):
        return None
