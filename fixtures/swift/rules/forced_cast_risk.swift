func castLoose(_ value: Any) -> Int {
    return value as! Int
}

func castGuarded(_ value: Any) -> Int {
    if value is Int {
        return value as! Int
    }
    return 0
}
