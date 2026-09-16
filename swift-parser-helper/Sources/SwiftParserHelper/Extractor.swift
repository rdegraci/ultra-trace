import Foundation
import SwiftParser
import SwiftSyntax

struct SourceSpanDict {
    let startLine: Int
    let startColumn: Int
    let endLine: Int
    let endColumn: Int

    func asDict() -> [String: Any] {
        [
            "start_line": startLine,
            "start_column": startColumn,
            "end_line": endLine,
            "end_column": endColumn,
        ]
    }
}

final class SpikeExtractor: SyntaxVisitor {
    private let converter: SourceLocationConverter
    private(set) var types: [[String: Any]] = []
    private(set) var functions: [[String: Any]] = []
    private(set) var markers: [[String: Any]] = []
    private(set) var calls: [[String: Any]] = []
    private(set) var unsupported: [[String: Any]] = []
    private(set) var sharedMutables: [[String: Any]] = []

    private var typeStack: [String] = []
    private var functionDepth = 0

    init(converter: SourceLocationConverter) {
        self.converter = converter
        super.init(viewMode: .sourceAccurate)
    }

    private func span(of node: some SyntaxProtocol) -> SourceSpanDict {
        let start = node.startLocation(converter: converter, afterLeadingTrivia: true)
        let end = node.endLocation(converter: converter, afterTrailingTrivia: false)
        return SourceSpanDict(
            startLine: start.line,
            startColumn: start.column,
            endLine: end.line,
            endColumn: end.column
        )
    }

    private func attributeNames(from attributes: AttributeListSyntax) -> [String] {
        var names: [String] = []
        for element in attributes {
            guard case let .attribute(attr) = element else { continue }
            names.append(attr.attributeName.trimmedDescription)
        }
        return names
    }

    private func hasNonisolated(_ modifiers: DeclModifierListSyntax) -> Bool {
        modifiers.contains { $0.name.text == "nonisolated" }
    }

    private func hasStatic(_ modifiers: DeclModifierListSyntax) -> Bool {
        modifiers.contains { $0.name.text == "static" }
    }

    private func recordType(
        kind: String,
        name: String,
        node: some SyntaxProtocol,
        attributes: AttributeListSyntax,
        modifiers: DeclModifierListSyntax
    ) {
        var item = span(of: node).asDict()
        item["kind"] = kind
        item["name"] = name
        item["attributes"] = attributeNames(from: attributes)
        item["nonisolated"] = hasNonisolated(modifiers)
        types.append(item)
    }

    private func recordFunction(
        kind: String,
        name: String,
        node: some SyntaxProtocol,
        body: CodeBlockSyntax?,
        parameters: [[String: Any]] = [],
        returnAnnotation: String? = nil,
        attributes: AttributeListSyntax = AttributeListSyntax([]),
        modifiers: DeclModifierListSyntax = DeclModifierListSyntax([])
    ) {
        var item = span(of: node).asDict()
        item["kind"] = kind
        item["name"] = name
        item["parameters"] = parameters
        item["attributes"] = attributeNames(from: attributes)
        item["nonisolated"] = hasNonisolated(modifiers)
        if let returnAnnotation {
            item["return_annotation"] = returnAnnotation
        } else {
            item["return_annotation"] = NSNull()
        }
        if let parent = typeStack.last {
            item["parent_type"] = parent
        } else {
            item["parent_type"] = NSNull()
        }
        if let body {
            let bodySpan = span(of: body)
            item["body_start_line"] = bodySpan.startLine
            item["body_start_column"] = bodySpan.startColumn
            item["body_end_line"] = bodySpan.endLine
            item["body_end_column"] = bodySpan.endColumn
            item["statements"] = SyntaxEncoding.encodeCodeBlock(body, converter: converter)
        } else {
            item["body_start_line"] = NSNull()
            item["body_start_column"] = NSNull()
            item["body_end_line"] = NSNull()
            item["body_end_column"] = NSNull()
            item["statements"] = [] as [Any]
        }
        functions.append(item)
    }

    private func recordSharedMutable(
        name: String,
        node: some SyntaxProtocol,
        attributes: AttributeListSyntax,
        modifiers: DeclModifierListSyntax
    ) {
        var item = span(of: node).asDict()
        item["name"] = name
        item["is_static"] = hasStatic(modifiers)
        item["attributes"] = attributeNames(from: attributes)
        item["nonisolated"] = hasNonisolated(modifiers)
        if let parent = typeStack.last {
            item["parent_type"] = parent
        } else {
            item["parent_type"] = NSNull()
        }
        sharedMutables.append(item)
    }

    private func recordMarker(kind: String, node: some SyntaxProtocol, detail: String? = nil) {
        var item = span(of: node).asDict()
        item["kind"] = kind
        if let detail {
            item["detail"] = detail
        }
        markers.append(item)
    }

    private func recordUnsupported(category: String, detail: String, node: some SyntaxProtocol) {
        var item = span(of: node).asDict()
        item["category"] = category
        item["detail"] = detail
        unsupported.append(item)
    }

    private func recordCall(callee: String, node: some SyntaxProtocol) {
        var item = span(of: node).asDict()
        item["callee"] = callee
        calls.append(item)
    }

    // MARK: - Types

    override func visit(_ node: ClassDeclSyntax) -> SyntaxVisitorContinueKind {
        recordType(
            kind: "class",
            name: node.name.text,
            node: node,
            attributes: node.attributes,
            modifiers: node.modifiers
        )
        typeStack.append(node.name.text)
        return .visitChildren
    }

    override func visitPost(_ node: ClassDeclSyntax) {
        _ = typeStack.popLast()
    }

    override func visit(_ node: StructDeclSyntax) -> SyntaxVisitorContinueKind {
        recordType(
            kind: "struct",
            name: node.name.text,
            node: node,
            attributes: node.attributes,
            modifiers: node.modifiers
        )
        typeStack.append(node.name.text)
        return .visitChildren
    }

    override func visitPost(_ node: StructDeclSyntax) {
        _ = typeStack.popLast()
    }

    override func visit(_ node: EnumDeclSyntax) -> SyntaxVisitorContinueKind {
        recordType(
            kind: "enum",
            name: node.name.text,
            node: node,
            attributes: node.attributes,
            modifiers: node.modifiers
        )
        typeStack.append(node.name.text)
        return .visitChildren
    }

    override func visitPost(_ node: EnumDeclSyntax) {
        _ = typeStack.popLast()
    }

    override func visit(_ node: ActorDeclSyntax) -> SyntaxVisitorContinueKind {
        recordType(
            kind: "actor",
            name: node.name.text,
            node: node,
            attributes: node.attributes,
            modifiers: node.modifiers
        )
        typeStack.append(node.name.text)
        return .visitChildren
    }

    override func visitPost(_ node: ActorDeclSyntax) {
        _ = typeStack.popLast()
    }

    override func visit(_ node: ProtocolDeclSyntax) -> SyntaxVisitorContinueKind {
        recordType(
            kind: "protocol",
            name: node.name.text,
            node: node,
            attributes: node.attributes,
            modifiers: node.modifiers
        )
        typeStack.append(node.name.text)
        return .visitChildren
    }

    override func visitPost(_ node: ProtocolDeclSyntax) {
        _ = typeStack.popLast()
    }

    override func visit(_ node: ExtensionDeclSyntax) -> SyntaxVisitorContinueKind {
        let name = node.extendedType.trimmedDescription
        recordType(
            kind: "extension",
            name: name,
            node: node,
            attributes: node.attributes,
            modifiers: node.modifiers
        )
        typeStack.append(name)
        return .visitChildren
    }

    override func visitPost(_ node: ExtensionDeclSyntax) {
        _ = typeStack.popLast()
    }

    // MARK: - Shared mutable candidates (type / file scope vars)

    override func visit(_ node: VariableDeclSyntax) -> SyntaxVisitorContinueKind {
        guard functionDepth == 0 else { return .visitChildren }
        guard node.bindingSpecifier.text == "var" else { return .visitChildren }
        for binding in node.bindings {
            guard let pattern = binding.pattern.as(IdentifierPatternSyntax.self) else {
                continue
            }
            recordSharedMutable(
                name: pattern.identifier.text,
                node: node,
                attributes: node.attributes,
                modifiers: node.modifiers
            )
        }
        return .visitChildren
    }

    // MARK: - Functions

    override func visit(_ node: FunctionDeclSyntax) -> SyntaxVisitorContinueKind {
        functionDepth += 1
        recordFunction(
            kind: "function",
            name: node.name.text,
            node: node,
            body: node.body,
            parameters: SyntaxEncoding.encodeParameters(
                node.signature.parameterClause,
                converter: converter
            ),
            returnAnnotation: node.signature.returnClause?.type.trimmedDescription,
            attributes: node.attributes,
            modifiers: node.modifiers
        )
        return .visitChildren
    }

    override func visitPost(_ node: FunctionDeclSyntax) {
        functionDepth -= 1
    }

    override func visit(_ node: InitializerDeclSyntax) -> SyntaxVisitorContinueKind {
        functionDepth += 1
        recordFunction(
            kind: "initializer",
            name: "init",
            node: node,
            body: node.body,
            parameters: SyntaxEncoding.encodeParameters(
                node.signature.parameterClause,
                converter: converter
            ),
            returnAnnotation: nil,
            attributes: node.attributes,
            modifiers: node.modifiers
        )
        return .visitChildren
    }

    override func visitPost(_ node: InitializerDeclSyntax) {
        functionDepth -= 1
    }

    override func visit(_ node: DeinitializerDeclSyntax) -> SyntaxVisitorContinueKind {
        functionDepth += 1
        recordFunction(kind: "function", name: "deinit", node: node, body: node.body)
        return .visitChildren
    }

    override func visitPost(_ node: DeinitializerDeclSyntax) {
        functionDepth -= 1
    }

    override func visit(_ node: AccessorDeclSyntax) -> SyntaxVisitorContinueKind {
        functionDepth += 1
        let name = node.accessorSpecifier.text
        recordFunction(
            kind: "accessor",
            name: name,
            node: node,
            body: node.body,
            attributes: node.attributes
        )
        return .visitChildren
    }

    override func visitPost(_ node: AccessorDeclSyntax) {
        functionDepth -= 1
    }

    // MARK: - Markers / calls

    override func visit(_ node: ForceUnwrapExprSyntax) -> SyntaxVisitorContinueKind {
        recordMarker(kind: "force_unwrap", node: node)
        return .visitChildren
    }

    override func visit(_ node: TryExprSyntax) -> SyntaxVisitorContinueKind {
        if node.questionOrExclamationMark?.tokenKind == .exclamationMark {
            recordMarker(kind: "try_bang", node: node, detail: "try!")
        }
        return .visitChildren
    }

    override func visit(_ node: AsExprSyntax) -> SyntaxVisitorContinueKind {
        if node.questionOrExclamationMark?.tokenKind == .exclamationMark {
            recordMarker(kind: "as_bang", node: node, detail: "as!")
        }
        return .visitChildren
    }

    override func visit(_ node: UnresolvedAsExprSyntax) -> SyntaxVisitorContinueKind {
        // Parser emits unresolved `as`/`as!`/`as?` inside SequenceExpr before folding.
        if node.questionOrExclamationMark?.tokenKind == .exclamationMark {
            recordMarker(kind: "as_bang", node: node, detail: "as!")
        }
        return .visitChildren
    }

    override func visit(_ node: SubscriptCallExprSyntax) -> SyntaxVisitorContinueKind {
        recordMarker(kind: "subscript", node: node)
        return .visitChildren
    }

    override func visit(_ node: AwaitExprSyntax) -> SyntaxVisitorContinueKind {
        recordMarker(kind: "await", node: node)
        return .visitChildren
    }

    override func visit(_ node: FunctionCallExprSyntax) -> SyntaxVisitorContinueKind {
        let callee = node.calledExpression.trimmedDescription
        recordCall(callee: callee, node: node)
        return .visitChildren
    }

    // MARK: - Unsupported signals (explicit, not silent)

    override func visit(_ node: MacroExpansionExprSyntax) -> SyntaxVisitorContinueKind {
        recordUnsupported(
            category: "macro",
            detail: "#\(node.macroName.text)",
            node: node
        )
        return .visitChildren
    }

    override func visit(_ node: MacroExpansionDeclSyntax) -> SyntaxVisitorContinueKind {
        recordUnsupported(
            category: "macro",
            detail: "#\(node.macroName.text)",
            node: node
        )
        return .visitChildren
    }

    override func visit(_ node: AttributeSyntax) -> SyntaxVisitorContinueKind {
        let name = node.attributeName.trimmedDescription
        let builderLike: Set<String> = [
            "resultBuilder",
            "ViewBuilder",
            "SceneBuilder",
            "CommandsBuilder",
            "ToolbarContentBuilder",
            "freestanding",
            "attached",
        ]
        if builderLike.contains(name) || name.hasSuffix("Builder") {
            recordUnsupported(
                category: "result_builder_or_macro_attr",
                detail: "@\(name)",
                node: node
            )
        }
        if name == "propertyWrapper" {
            recordUnsupported(category: "property_wrapper", detail: "@\(name)", node: node)
        }
        // Common property wrappers treated as best-effort / unsupported for Core spike.
        let wrapperLike: Set<String> = [
            "State", "Binding", "ObservedObject", "StateObject", "EnvironmentObject",
            "Environment", "Published", "AppStorage", "SceneStorage", "FocusState",
        ]
        if wrapperLike.contains(name) {
            recordUnsupported(category: "property_wrapper", detail: "@\(name)", node: node)
        }
        return .visitChildren
    }

    override func visit(_ node: OperatorDeclSyntax) -> SyntaxVisitorContinueKind {
        recordUnsupported(
            category: "custom_operator",
            detail: node.trimmedDescription,
            node: node
        )
        return .skipChildren
    }
}

enum FileExtractor {
    static func extract(path: String, relativePath: String, source: String) -> [String: Any] {
        let tree = Parser.parse(source: source)
        let converter = SourceLocationConverter(fileName: path, tree: tree)
        let extractor = SpikeExtractor(converter: converter)
        extractor.walk(tree)

        let lineCount = source.split(separator: "\n", omittingEmptySubsequences: false).count
        // Deterministic ordering for repeated runs.
        let types = extractor.types.sorted { lhs, rhs in
            compareSpan(lhs, rhs)
        }
        let functions = extractor.functions.sorted { lhs, rhs in
            compareSpan(lhs, rhs)
        }
        let markers = extractor.markers.sorted { lhs, rhs in
            compareSpan(lhs, rhs)
        }
        let calls = extractor.calls.sorted { lhs, rhs in
            compareSpan(lhs, rhs)
        }
        let unsupported = extractor.unsupported.sorted { lhs, rhs in
            compareSpan(lhs, rhs)
        }
        let sharedMutables = extractor.sharedMutables.sorted { lhs, rhs in
            compareSpan(lhs, rhs)
        }

        return [
            "path": relativePath,
            "absolute_path": path,
            "parse_ok": true,
            "line_count": lineCount,
            "types": types,
            "functions": functions,
            "markers": markers,
            "calls": calls,
            "unsupported": unsupported,
            "shared_mutables": sharedMutables,
            "diagnostics": [] as [Any],
        ]
    }

    private static func compareSpan(_ lhs: [String: Any], _ rhs: [String: Any]) -> Bool {
        let lLine = lhs["start_line"] as? Int ?? 0
        let rLine = rhs["start_line"] as? Int ?? 0
        if lLine != rLine { return lLine < rLine }
        let lCol = lhs["start_column"] as? Int ?? 0
        let rCol = rhs["start_column"] as? Int ?? 0
        if lCol != rCol { return lCol < rCol }
        let lKind = (lhs["kind"] as? String)
            ?? (lhs["category"] as? String)
            ?? (lhs["callee"] as? String)
            ?? ""
        let rKind = (rhs["kind"] as? String)
            ?? (rhs["category"] as? String)
            ?? (rhs["callee"] as? String)
            ?? ""
        return lKind < rKind
    }
}
