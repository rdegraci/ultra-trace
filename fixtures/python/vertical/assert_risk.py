def guarded_by_assert(flag: bool) -> int:
    assert flag
    return 1


def always_false_assert() -> int:
    assert False
    return 0
