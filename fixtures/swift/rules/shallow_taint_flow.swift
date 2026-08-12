struct URLQueryItem {
    var value: String
}

enum FileManager {
    static func createFile(atPath: String) {}
}

func leakQuery(_ item: URLQueryItem) {
    FileManager.createFile(atPath: item.value)
}

func sanitizedQuery(_ item: URLQueryItem) {
    let safe = item.value.addingPercentEncoding(withAllowedCharacters: "ok") ?? ""
    FileManager.createFile(atPath: safe)
}

func staticPath() {
    FileManager.createFile(atPath: "/tmp/ok")
}
