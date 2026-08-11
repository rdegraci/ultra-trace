import Foundation

enum JSONEncoding {
    static func encode(_ value: Any) throws -> Data {
        let options: JSONSerialization.WritingOptions = [.sortedKeys]
        guard JSONSerialization.isValidJSONObject(value) else {
            throw NSError(
                domain: "swift-parser-helper",
                code: 1,
                userInfo: [NSLocalizedDescriptionKey: "Invalid JSON object"]
            )
        }
        return try JSONSerialization.data(withJSONObject: value, options: options)
    }

    static func encodeToString(_ value: Any) throws -> String {
        let data = try encode(value)
        guard let text = String(data: data, encoding: .utf8) else {
            throw NSError(
                domain: "swift-parser-helper",
                code: 2,
                userInfo: [NSLocalizedDescriptionKey: "UTF-8 encode failed"]
            )
        }
        return text
    }
}
