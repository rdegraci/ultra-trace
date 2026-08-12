func deadIfFalse() -> Int {
    if false {
        return 1
    }
    return 0
}

func deadAfterFact() -> Int {
    let flag = false
    if flag {
        return 1
    }
    return 0
}

func liveCompare(_ n: Int) -> String {
    if n == 0 {
        return "zero"
    }
    return "other"
}
