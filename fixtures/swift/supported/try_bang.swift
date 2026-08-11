enum Boom: Error {
    case failed
}

func mayFail(_ ok: Bool) throws -> Int {
    if ok { return 1 }
    throw Boom.failed
}

func caller() -> Int {
    return try! mayFail(true)
}
