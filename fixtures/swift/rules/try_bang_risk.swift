enum ParseError: Error {
    case bad
}

func parse(_ text: String) throws -> Int {
    if text.isEmpty { throw ParseError.bad }
    return 1
}

func crashParse(_ text: String) -> Int {
    return try! parse(text)
}

func handledParse(_ text: String) -> Int {
    do {
        return try parse(text)
    } catch {
        return 0
    }
}
