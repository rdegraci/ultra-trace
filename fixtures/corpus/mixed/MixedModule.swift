import Foundation

@resultBuilder
enum RowBuilder {
    static func buildBlock(_ components: String...) -> [String] {
        Array(components)
    }
}

struct MixedService {
    func load(_ data: Data) throws -> [String: Any] {
        let obj = try JSONSerialization.jsonObject(with: data)
        return obj as! [String: Any]
    }

    func values(_ items: [Int]) -> Int {
        return items[0]
    }
}

@RowBuilder
func rows() -> [String] {
    "one"
    "two"
}
