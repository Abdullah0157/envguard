def initials(full_name):
    return "".join(part[0].upper() + "." for part in full_name.split())
