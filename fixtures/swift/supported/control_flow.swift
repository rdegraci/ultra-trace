func classify(_ n: Int) -> String {
    guard n >= 0 else {
        return "neg"
    }
    if n == 0 {
        return "zero"
    } else if n < 10 {
        return "small"
    }
    switch n {
    case 10:
        return "ten"
    default:
        return "big"
    }
}

func loopSum(_ values: [Int]) -> Int {
    var total = 0
    for v in values {
        total += v
    }
    var i = 0
    while i < values.count {
        i += 1
    }
    return total
}
