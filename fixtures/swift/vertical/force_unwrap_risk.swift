// Vertical-slice fixture for swift.force_unwrap_risk

func loadTitle(_ value: String?) -> String {
    return value!
}

func alwaysNil() -> String {
    let value: String? = nil
    return value!
}

func provenLiteral() -> String {
    let value: String? = "ok"
    return value!
}

func guardedTitle(_ value: String?) -> String {
    guard let value = value else {
        return ""
    }
    return value
}
