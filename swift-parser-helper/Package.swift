// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "swift-parser-helper",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "swift-parser-helper", targets: ["SwiftParserHelper"]),
    ],
    dependencies: [
        // Swift 6.2 ↔ swift-syntax 602.x (see TOOLCHAIN.md).
        .package(url: "https://github.com/swiftlang/swift-syntax.git", exact: "602.0.0"),
    ],
    targets: [
        .executableTarget(
            name: "SwiftParserHelper",
            dependencies: [
                .product(name: "SwiftSyntax", package: "swift-syntax"),
                .product(name: "SwiftParser", package: "swift-syntax"),
            ],
            path: "Sources/SwiftParserHelper"
        ),
    ]
)
