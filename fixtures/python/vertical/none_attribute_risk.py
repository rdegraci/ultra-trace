def read_title(value: str | None = None) -> str:
    return value.upper()


def always_none() -> str:
    value = None
    return value.strip()


def guarded(value: str | None) -> str:
    if value is None:
        return ""
    return value.upper()
