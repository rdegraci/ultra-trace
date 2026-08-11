@resultBuilder
enum ToyBuilder {
    static func buildBlock(_ components: String...) -> String {
        components.joined()
    }
}

@ToyBuilder
func buildLabel() -> String {
    "a"
    "b"
}
