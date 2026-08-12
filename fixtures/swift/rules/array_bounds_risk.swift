func unguardedIndex(_ items: [Int], index: Int) -> Int {
    return items[index]
}

func guardedIndex(_ items: [Int], index: Int) -> Int {
    guard index < items.count else { return 0 }
    return items[index]
}

func literalSafe() -> Int {
    let items = [1, 2, 3]
    return items[0]
}

func literalOOB() -> Int {
    let items = [1]
    return items[4]
}
