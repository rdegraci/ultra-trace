import Foundation
import SwiftSyntax

enum SyntaxEncoding {
    static func span(of node: some SyntaxProtocol, converter: SourceLocationConverter) -> [String: Any] {
        let start = node.startLocation(converter: converter, afterLeadingTrivia: true)
        let end = node.endLocation(converter: converter, afterTrailingTrivia: false)
        return [
            "start_line": start.line,
            "start_column": start.column,
            "end_line": end.line,
            "end_column": end.column,
        ]
    }

    static func encodeParameters(
        _ clause: FunctionParameterClauseSyntax,
        converter: SourceLocationConverter
    ) -> [[String: Any]] {
        clause.parameters.map { param in
            var item = span(of: param, converter: converter)
            let first = param.firstName.text
            let local = param.secondName?.text ?? first
            item["external_name"] = first
            item["local_name"] = local
            item["type_annotation"] = param.type.trimmedDescription
            return item
        }
    }

    static func encodeCodeBlock(
        _ block: CodeBlockSyntax,
        converter: SourceLocationConverter
    ) -> [[String: Any]] {
        encodeItems(block.statements, converter: converter)
    }

    static func encodeItems(
        _ items: CodeBlockItemListSyntax,
        converter: SourceLocationConverter
    ) -> [[String: Any]] {
        items.compactMap { encodeItem($0, converter: converter) }
    }

    static func encodeItem(
        _ item: CodeBlockItemSyntax,
        converter: SourceLocationConverter
    ) -> [String: Any]? {
        switch item.item {
        case .decl(let decl):
            if let variable = decl.as(VariableDeclSyntax.self) {
                return encodeVariable(variable, converter: converter)
            }
            return nil
        case .stmt(let stmt):
            return encodeStmt(stmt, converter: converter)
        case .expr(let expr):
            if let assignment = encodeAssignment(expr, converter: converter) {
                return assignment
            }
            if let ifExpr = expr.as(IfExprSyntax.self) {
                return encodeIf(ifExpr, converter: converter)
            }
            if let switchExpr = expr.as(SwitchExprSyntax.self) {
                return encodeSwitch(switchExpr, converter: converter)
            }
            var item = span(of: expr, converter: converter)
            item["kind"] = "expression"
            item["expression"] = encodeExpr(expr, converter: converter)
            return item
        }
    }

    static func encodeVariable(
        _ decl: VariableDeclSyntax,
        converter: SourceLocationConverter
    ) -> [String: Any] {
        var item = span(of: decl, converter: converter)
        item["kind"] = "variable_declaration"
        let names = decl.bindings.compactMap { binding -> String? in
            binding.pattern.as(IdentifierPatternSyntax.self)?.identifier.text
        }
        item["names"] = names
        if let first = decl.bindings.first {
            item["type_annotation"] = first.typeAnnotation?.type.trimmedDescription as Any
            if let value = first.initializer?.value {
                item["initializer"] = encodeExpr(value, converter: converter)
            }
        }
        return item
    }

    static func encodeAssignment(
        _ expr: ExprSyntax,
        converter: SourceLocationConverter
    ) -> [String: Any]? {
        if let infix = expr.as(InfixOperatorExprSyntax.self),
           infix.operator.as(AssignmentExprSyntax.self) != nil
        {
            var item = span(of: expr, converter: converter)
            item["kind"] = "assignment"
            item["target"] = encodeExpr(infix.leftOperand, converter: converter)
            item["value"] = encodeExpr(infix.rightOperand, converter: converter)
            return item
        }
        if let seq = expr.as(SequenceExprSyntax.self) {
            let elements = Array(seq.elements)
            if elements.count >= 3,
               elements[1].is(AssignmentExprSyntax.self)
            {
                var item = span(of: expr, converter: converter)
                item["kind"] = "assignment"
                item["target"] = encodeExpr(elements[0], converter: converter)
                item["value"] = encodeExpr(elements[2], converter: converter)
                return item
            }
        }
        return nil
    }

    static func encodeStmt(
        _ stmt: StmtSyntax,
        converter: SourceLocationConverter
    ) -> [String: Any] {
        if let node = stmt.as(ReturnStmtSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "return_statement"
            if let value = node.expression {
                item["value"] = encodeExpr(value, converter: converter)
            }
            return item
        }
        if let node = stmt.as(ThrowStmtSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "throw_statement"
            item["value"] = encodeExpr(node.expression, converter: converter)
            return item
        }
        if let node = stmt.as(GuardStmtSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "guard_statement"
            item["condition"] = encodeConditions(node.conditions, converter: converter)
            item["else_statements"] = encodeCodeBlock(node.body, converter: converter)
            return item
        }
        if let node = stmt.as(ForStmtSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "for_loop"
            item["condition"] = encodeExpr(node.sequence, converter: converter)
            item["statements"] = encodeCodeBlock(node.body, converter: converter)
            return item
        }
        if let node = stmt.as(WhileStmtSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "while_loop"
            item["condition"] = encodeConditions(node.conditions, converter: converter)
            item["statements"] = encodeCodeBlock(node.body, converter: converter)
            return item
        }
        if let node = stmt.as(RepeatStmtSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "repeat_loop"
            item["condition"] = encodeExpr(node.condition, converter: converter)
            item["statements"] = encodeCodeBlock(node.body, converter: converter)
            return item
        }
        if let node = stmt.as(BreakStmtSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "break_statement"
            if let label = node.label {
                item["label"] = label.text
            }
            return item
        }
        if let node = stmt.as(ContinueStmtSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "continue_statement"
            if let label = node.label {
                item["label"] = label.text
            }
            return item
        }
        if let node = stmt.as(DeferStmtSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "defer_statement"
            item["statements"] = encodeCodeBlock(node.body, converter: converter)
            return item
        }
        if let node = stmt.as(DoStmtSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "do_catch_statement"
            item["statements"] = encodeCodeBlock(node.body, converter: converter)
            let catches: [[String: Any]] = node.catchClauses.map { clause in
                ["statements": encodeCodeBlock(clause.body, converter: converter)]
            }
            item["catches"] = catches
            return item
        }
        if let node = stmt.as(ExpressionStmtSyntax.self) {
            if let assignment = encodeAssignment(node.expression, converter: converter) {
                return assignment
            }
            if let ifExpr = node.expression.as(IfExprSyntax.self) {
                return encodeIf(ifExpr, converter: converter)
            }
            if let switchExpr = node.expression.as(SwitchExprSyntax.self) {
                return encodeSwitch(switchExpr, converter: converter)
            }
            var item = span(of: node, converter: converter)
            item["kind"] = "expression"
            item["expression"] = encodeExpr(node.expression, converter: converter)
            return item
        }
        var item = span(of: stmt, converter: converter)
        item["kind"] = "expression"
        item["expression"] = [
            "kind": "unknown",
            "text": stmt.trimmedDescription,
        ].merging(span(of: stmt, converter: converter)) { _, new in new }
        return item
    }

    static func encodeIf(
        _ node: IfExprSyntax,
        converter: SourceLocationConverter
    ) -> [String: Any] {
        var item = span(of: node, converter: converter)
        item["kind"] = "if_statement"
        item["condition"] = encodeConditions(node.conditions, converter: converter)
        item["then_statements"] = encodeCodeBlock(node.body, converter: converter)
        if let elseBody = node.elseBody {
            switch elseBody {
            case .ifExpr(let nested):
                item["else_statements"] = [encodeIf(nested, converter: converter)]
            case .codeBlock(let block):
                item["else_statements"] = encodeCodeBlock(block, converter: converter)
            }
        }
        return item
    }

    static func encodeSwitch(
        _ node: SwitchExprSyntax,
        converter: SourceLocationConverter
    ) -> [String: Any] {
        var item = span(of: node, converter: converter)
        item["kind"] = "switch_statement"
        item["subject"] = encodeExpr(node.subject, converter: converter)
        var cases: [[String: Any]] = []
        for element in node.cases {
            if let switchCase = element.as(SwitchCaseSyntax.self) {
                var caseItem: [String: Any] = [:]
                switch switchCase.label {
                case .case(let label):
                    caseItem["pattern"] = label.trimmedDescription
                case .default:
                    caseItem["pattern"] = "default"
                }
                caseItem["statements"] = encodeItems(switchCase.statements, converter: converter)
                cases.append(caseItem)
            }
        }
        item["cases"] = cases
        return item
    }

    static func encodeConditions(
        _ conditions: ConditionElementListSyntax,
        converter: SourceLocationConverter
    ) -> [String: Any] {
        if let first = conditions.first {
            switch first.condition {
            case .expression(let expr):
                return encodeExpr(expr, converter: converter)
            default:
                var item = span(of: first, converter: converter)
                item["kind"] = "unknown"
                item["text"] = first.trimmedDescription
                return item
            }
        }
        return ["kind": "unknown", "text": "", "start_line": 0, "start_column": 0, "end_line": 0, "end_column": 0]
    }

    static func encodeExpr(
        _ expr: ExprSyntax,
        converter: SourceLocationConverter
    ) -> [String: Any] {
        if let node = expr.as(DeclReferenceExprSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "identifier"
            item["name"] = node.baseName.text
            return item
        }
        if let node = expr.as(MemberAccessExprSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "member_access"
            item["member"] = node.declName.baseName.text
            if let base = node.base {
                item["base"] = encodeExpr(base, converter: converter)
            }
            return item
        }
        if let node = expr.as(FunctionCallExprSyntax.self) {
            return encodeCall(node, converter: converter, tryFlags: (false, false, false))
        }
        if let node = expr.as(TryExprSyntax.self) {
            let isForce = node.questionOrExclamationMark?.tokenKind == .exclamationMark
            let isOpt = node.questionOrExclamationMark?.tokenKind == .postfixQuestionMark
            if let call = node.expression.as(FunctionCallExprSyntax.self) {
                let encoded = encodeCall(
                    call,
                    converter: converter,
                    tryFlags: (true, isOpt, isForce)
                )
                // Prefer the try! span for the outer wrapper when present.
                var wrapper = span(of: node, converter: converter)
                wrapper["kind"] = "try_expression"
                wrapper["style"] = isForce ? "try!" : (isOpt ? "try?" : "try")
                wrapper["operand"] = encoded
                return wrapper
            }
            var item = span(of: node, converter: converter)
            item["kind"] = "try_expression"
            item["style"] = isForce ? "try!" : (isOpt ? "try?" : "try")
            item["operand"] = encodeExpr(node.expression, converter: converter)
            return item
        }
        if let node = expr.as(AwaitExprSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "await"
            item["operand"] = encodeExpr(node.expression, converter: converter)
            return item
        }
        if let node = expr.as(ForceUnwrapExprSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "force_unwrap"
            item["operand"] = encodeExpr(node.expression, converter: converter)
            return item
        }
        if let node = expr.as(OptionalChainingExprSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "optional_chain"
            item["operand"] = encodeExpr(node.expression, converter: converter)
            return item
        }
        if let node = expr.as(AsExprSyntax.self) {
            var item = span(of: node, converter: converter)
            if node.questionOrExclamationMark?.tokenKind == .exclamationMark {
                item["kind"] = "forced_cast"
            } else {
                item["kind"] = "unknown"
            }
            item["operand"] = encodeExpr(node.expression, converter: converter)
            item["type_name"] = node.type.trimmedDescription
            return item
        }
        if let node = expr.as(SubscriptCallExprSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "subscript"
            item["base"] = encodeExpr(node.calledExpression, converter: converter)
            item["arguments"] = node.arguments.map { encodeExpr($0.expression, converter: converter) }
            return item
        }
        if let node = expr.as(IntegerLiteralExprSyntax.self) {
            return literal(node, text: node.literal.text, converter: converter)
        }
        if let node = expr.as(FloatLiteralExprSyntax.self) {
            return literal(node, text: node.literal.text, converter: converter)
        }
        if let node = expr.as(BooleanLiteralExprSyntax.self) {
            return literal(node, text: node.literal.text, converter: converter)
        }
        if let node = expr.as(StringLiteralExprSyntax.self) {
            return literal(node, text: node.trimmedDescription, converter: converter)
        }
        if let node = expr.as(NilLiteralExprSyntax.self) {
            return literal(node, text: "nil", converter: converter)
        }
        if let node = expr.as(ArrayExprSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "array_literal"
            item["elements"] = node.elements.map { encodeExpr($0.expression, converter: converter) }
            return item
        }
        if let node = expr.as(DictionaryExprSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "dictionary_literal"
            return item
        }
        if let node = expr.as(ClosureExprSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "closure_expression"
            return item
        }
        if let node = expr.as(InfixOperatorExprSyntax.self) {
            let opText = node.operator.trimmedDescription
            var item = span(of: node, converter: converter)
            if opText == "??" {
                item["kind"] = "nil_coalescing"
                item["left"] = encodeExpr(node.leftOperand, converter: converter)
                item["right"] = encodeExpr(node.rightOperand, converter: converter)
                return item
            }
            item["kind"] = "binary_operator"
            item["operator"] = opText
            item["left"] = encodeExpr(node.leftOperand, converter: converter)
            item["right"] = encodeExpr(node.rightOperand, converter: converter)
            return item
        }
        if let node = expr.as(PrefixOperatorExprSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "unary_operator"
            item["operator"] = node.operator.text
            item["operand"] = encodeExpr(node.expression, converter: converter)
            return item
        }
        if let node = expr.as(IfExprSyntax.self) {
            // If-expression used as a value; still expose the if structure as unknown text.
            var item = span(of: node, converter: converter)
            item["kind"] = "unknown"
            item["text"] = node.trimmedDescription
            return item
        }
        if let node = expr.as(SequenceExprSyntax.self) {
            return encodeSequence(node, converter: converter)
        }
        if let node = expr.as(TupleExprSyntax.self), node.elements.count == 1,
           let only = node.elements.first
        {
            return encodeExpr(only.expression, converter: converter)
        }
        if let node = expr.as(SuperExprSyntax.self) {
            var item = span(of: node, converter: converter)
            item["kind"] = "identifier"
            item["name"] = "super"
            return item
        }
        var item = span(of: expr, converter: converter)
        item["kind"] = "unknown"
        item["text"] = expr.trimmedDescription
        return item
    }

    static func encodeCall(
        _ node: FunctionCallExprSyntax,
        converter: SourceLocationConverter,
        tryFlags: (isTry: Bool, isOpt: Bool, isForce: Bool)
    ) -> [String: Any] {
        var item = span(of: node, converter: converter)
        item["kind"] = "call"
        item["callee"] = encodeExpr(node.calledExpression, converter: converter)
        item["callee_text"] = node.calledExpression.trimmedDescription
        item["arguments"] = node.arguments.map { encodeExpr($0.expression, converter: converter) }
        item["is_try"] = tryFlags.isTry
        item["is_try_optional"] = tryFlags.isOpt
        item["is_try_force"] = tryFlags.isForce
        return item
    }

    static func encodeSequence(
        _ node: SequenceExprSyntax,
        converter: SourceLocationConverter
    ) -> [String: Any] {
        let elements = Array(node.elements)
        if elements.count >= 3 {
            let mid = elements[1]
            if let unresolvedAs = mid.as(UnresolvedAsExprSyntax.self),
               unresolvedAs.questionOrExclamationMark?.tokenKind == .exclamationMark
            {
                var item = span(of: node, converter: converter)
                item["kind"] = "forced_cast"
                item["operand"] = encodeExpr(elements[0], converter: converter)
                item["type_name"] = elements[2].trimmedDescription
                return item
            }
            if let bin = mid.as(BinaryOperatorExprSyntax.self) {
                let op = bin.operator.trimmedDescription
                var item = span(of: node, converter: converter)
                if op == "??" {
                    item["kind"] = "nil_coalescing"
                } else {
                    item["kind"] = "binary_operator"
                    item["operator"] = op
                }
                item["left"] = encodeExpr(elements[0], converter: converter)
                item["right"] = encodeExpr(elements[2], converter: converter)
                return item
            }
            if mid.is(AssignmentExprSyntax.self) {
                var item = span(of: node, converter: converter)
                item["kind"] = "unknown"
                item["text"] = node.trimmedDescription
                return item
            }
        }
        var item = span(of: node, converter: converter)
        item["kind"] = "unknown"
        item["text"] = node.trimmedDescription
        return item
    }

    private static func literal(
        _ node: some SyntaxProtocol,
        text: String,
        converter: SourceLocationConverter
    ) -> [String: Any] {
        var item = span(of: node, converter: converter)
        item["kind"] = "literal"
        item["text"] = text
        return item
    }
}
