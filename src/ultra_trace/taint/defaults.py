"""Starter iOS source / sink / sanitizer catalog for Core shallow taint."""

from __future__ import annotations

# Member/call substrings. Matching is conservative and config-overridable.
STARTER_SOURCE_PATTERNS: tuple[str, ...] = (
    "UITextField.text",
    "UITextView.text",
    "UISearchBar.text",
    "URLQueryItem.value",
    "URLComponents.query",
    "URLComponents.queryItems",
    "ProcessInfo.environment",
    "CommandLine.arguments",
    "UserDefaults.string",
    "UserDefaults.object",
    "WKScriptMessage.body",
    "Notification.userInfo",
    "JSONSerialization.jsonObject",
)

STARTER_SINK_PATTERNS: tuple[str, ...] = (
    "FileManager.default.createFile",
    "FileManager.createFile",
    "createFile",
    "write(to:",
    "String.write",
    "Data.write",
    "URLSession.shared.dataTask",
    "URLSession.dataTask",
    "dataTask",
    "WKWebView.loadHTMLString",
    "loadHTMLString",
    "evaluateJavaScript",
    "NSPredicate",
    "Process.launch",
)

STARTER_SANITIZER_PATTERNS: tuple[str, ...] = (
    "addingPercentEncoding",
    "addingPercentEncoding(withAllowedCharacters",
    "standardizedFileURL",
    "resolvingSymlinksInPath",
    "standardized",
    "escaped",
    "sanitized",
)

# Advanced pack expansions (merged on top of starter catalogs).
ADVANCED_SOURCE_PATTERNS: tuple[str, ...] = (
    "UIPasteboard.general.string",
    "UIPasteboard.string",
    "CNContact",
    "CLLocation",
    "CMMotionManager",
    "AVCapture",
    "HKHealthStore",
    "SecItemCopyMatching",
    "LAContext",
    "ASWebAuthenticationSession",
    "NFCNDEFReaderSession",
)

ADVANCED_SINK_PATTERNS: tuple[str, ...] = (
    "Process.launchPath",
    "Process.arguments",
    "NSTask.launch",
    "NSTask.launchPath",
    "sqlite3_exec",
    "FMDatabase.executeUpdate",
    "executeUpdate",
    "executeQuery",
    "JSContext.evaluateScript",
    "evaluateScript",
    "CNContactStore.enumerateContacts",
    "UIApplication.open",
    "openURL",
)

ADVANCED_SANITIZER_PATTERNS: tuple[str, ...] = (
    "CharacterSet.urlQueryAllowed",
    "whitelisted",
    "allowList",
    "allowlisted",
    "validated",
    "canonicalize",
    "pathExtension",
    "deletingLastPathComponent",
    "SQL escape",
    "sqlite3_bind",
)

CRITICAL_SINK_PATTERNS: tuple[str, ...] = (
    "evaluateJavaScript",
    "JSContext.evaluateScript",
    "evaluateScript",
    "Process.launchPath",
    "NSTask.launch",
    "sqlite3_exec",
)
