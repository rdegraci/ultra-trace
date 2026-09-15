// NS2 fixture: await on a path that later force-unwraps a previously-proven optional.
// After suspension, sequential nilness must not invent High.

func fetchTitle() async -> String {
    return "ok"
}

func unwrapAfterAwait() async -> String {
    let title: String? = "ok"
    _ = await fetchTitle()
    return title!
}

func sequentialNil() -> String {
    let title: String? = nil
    return title!
}
