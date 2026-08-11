import Foundation

@main
enum SwiftParserHelperMain {
    static func main() {
        do {
            try run(arguments: Array(CommandLine.arguments.dropFirst()))
        } catch {
            fputs("swift-parser-helper: \(error)\n", stderr)
            exit(2)
        }
    }

    private static func run(arguments: [String]) throws {
        if arguments.contains("--help") || arguments.contains("-h") {
            printHelp()
            return
        }
        if arguments.contains("--version") {
            try printVersion()
            return
        }

        var repoRoot: String?
        var inputFileList: String?
        var files: [String] = []
        var i = 0
        while i < arguments.count {
            let arg = arguments[i]
            switch arg {
            case "--repo-root":
                i += 1
                guard i < arguments.count else {
                    throw HelperError.usage("missing value for --repo-root")
                }
                repoRoot = arguments[i]
            case "--input-file-list":
                i += 1
                guard i < arguments.count else {
                    throw HelperError.usage("missing value for --input-file-list")
                }
                inputFileList = arguments[i]
            default:
                if arg.hasPrefix("-") {
                    throw HelperError.usage("unknown flag: \(arg)")
                }
                files.append(arg)
            }
            i += 1
        }

        guard let repoRoot else {
            throw HelperError.usage("--repo-root is required")
        }
        let rootURL = URL(fileURLWithPath: repoRoot).standardizedFileURL

        if let inputFileList {
            let listURL = URL(fileURLWithPath: inputFileList)
            let text = try String(contentsOf: listURL, encoding: .utf8)
            let listed = text
                .split(whereSeparator: \.isNewline)
                .map { String($0).trimmingCharacters(in: .whitespaces) }
                .filter { !$0.isEmpty && !$0.hasPrefix("#") }
            files.append(contentsOf: listed)
        }

        // Deterministic file order.
        let uniqueSorted = Array(Set(files)).sorted()
        guard !uniqueSorted.isEmpty else {
            throw HelperError.usage("no input files provided")
        }

        var fileRecords: [[String: Any]] = []
        var errors: [[String: Any]] = []

        for path in uniqueSorted {
            let fileURL: URL
            if path.hasPrefix("/") {
                fileURL = URL(fileURLWithPath: path).standardizedFileURL
            } else {
                fileURL = rootURL.appendingPathComponent(path).standardizedFileURL
            }
            let relative = relativePath(of: fileURL, to: rootURL)
            do {
                let source = try String(contentsOf: fileURL, encoding: .utf8)
                let record = FileExtractor.extract(
                    path: fileURL.path,
                    relativePath: relative,
                    source: source
                )
                fileRecords.append(record)
            } catch {
                errors.append([
                    "path": relative,
                    "message": "\(error)",
                ])
                fileRecords.append([
                    "path": relative,
                    "absolute_path": fileURL.path,
                    "parse_ok": false,
                    "line_count": 0,
                    "types": [] as [Any],
                    "functions": [] as [Any],
                    "markers": [] as [Any],
                    "calls": [] as [Any],
                    "unsupported": [] as [Any],
                    "diagnostics": [
                        [
                            "severity": "error",
                            "message": "failed to read or parse: \(error)",
                        ],
                    ],
                ])
            }
        }

        let toolchain = detectToolchain()
        let payload: [String: Any] = [
            "schema_version": HelperVersions.schemaVersion,
            "helper_version": HelperVersions.helperVersion,
            "parser_metadata": [
                "parser_name": HelperVersions.helperName,
                "parser_version": HelperVersions.helperVersion,
                "swift_syntax_version": HelperVersions.swiftSyntaxVersion,
                "toolchain_name": toolchain.name,
                "toolchain_version": toolchain.version,
                "invocation_mode": "subprocess-json",
                "supports_recovery": false,
            ],
            "files": fileRecords,
            "diagnostics": [] as [Any],
            "errors": errors,
        ]

        let json = try JSONEncoding.encodeToString(payload)
        print(json)

        if !errors.isEmpty {
            exit(1)
        }
    }

    private static func printHelp() {
        let text = """
        swift-parser-helper — Ultra-Trace Core SwiftSyntax spike helper

        Usage:
          swift-parser-helper --repo-root <path> --input-file-list <path>
          swift-parser-helper --repo-root <path> <file> [<file> ...]
          swift-parser-helper --version
          swift-parser-helper --help

        Emits versioned JSON on stdout. Fatal errors go to stderr with non-zero exit.
        """
        print(text)
    }

    private static func printVersion() throws {
        let toolchain = detectToolchain()
        let payload: [String: Any] = [
            "helper_name": HelperVersions.helperName,
            "helper_version": HelperVersions.helperVersion,
            "schema_version": HelperVersions.schemaVersion,
            "swift_syntax_version": HelperVersions.swiftSyntaxVersion,
            "toolchain_name": toolchain.name,
            "toolchain_version": toolchain.version,
        ]
        print(try JSONEncoding.encodeToString(payload))
    }

    private static func relativePath(of file: URL, to root: URL) -> String {
        let filePath = file.path
        let rootPath = root.path.hasSuffix("/") ? root.path : root.path + "/"
        if filePath.hasPrefix(rootPath) {
            return String(filePath.dropFirst(rootPath.count))
        }
        if filePath.hasPrefix(root.path) {
            var rel = String(filePath.dropFirst(root.path.count))
            if rel.hasPrefix("/") { rel.removeFirst() }
            return rel
        }
        return filePath
    }

    private static func detectToolchain() -> (name: String, version: String) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/swift")
        process.arguments = ["--version"]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        do {
            try process.run()
            process.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let text = String(data: data, encoding: .utf8)?
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            let first = text.split(separator: "\n", maxSplits: 1).first.map(String.init) ?? text
            return ("Apple Swift", first.isEmpty ? "unknown" : first)
        } catch {
            return ("Apple Swift", "unknown")
        }
    }
}

enum HelperError: Error, CustomStringConvertible {
    case usage(String)

    var description: String {
        switch self {
        case .usage(let message):
            return "usage error: \(message)"
        }
    }
}
