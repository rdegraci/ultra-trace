func firstItem(_ values: [Int]) -> Int {
    return values[0]
}

func fetch() async -> Int {
    return 42
}

func useFetch() async -> Int {
    return await fetch()
}
