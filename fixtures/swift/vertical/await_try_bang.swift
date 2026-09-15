// NS2 fixture: await on a path that later force-try's a throwing call.
// Unknown suspension must not invent High.

enum Boom: Error {
    case bad
}

func mayFail(_ ok: Bool) throws -> Int {
    if ok { return 1 }
    throw Boom.bad
}

func fetchFlag() async -> Bool {
    return false
}

func tryBangAfterAwait() async -> Int {
    _ = await fetchFlag()
    return try! mayFail(false)
}

func sequentialTryBang() -> Int {
    return try! mayFail(false)
}
