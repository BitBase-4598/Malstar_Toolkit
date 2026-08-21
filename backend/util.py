from datetime import datetime


def now_stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def letters_only(value):
    return "".join(ch for ch in (value or "") if ch.isalpha()).casefold()
