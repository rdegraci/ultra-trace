# swift-parser-helper toolchain notes

## Expectations (Slice 2 / Core MVP)

| Item | Pin / expectation |
|---|---|
| Host | macOS with Xcode (Core Swift analysis assumes macOS CI) |
| Swift toolchain | Apple Swift **6.2.x** (Xcode 26.x family) |
| SwiftSyntax | **602.0.0** (exact pin in `Package.swift`) |
| Helper version | **0.1.0** (`HelperVersions.helperVersion`) |
| JSON schema | **1.0** |

Python-side pin file (authoritative for CI drift checks):
[`../toolchain-pins/parser-helper.json`](../toolchain-pins/parser-helper.json)

## Drift risks

1. **SwiftSyntax vs compiler mismatch** — macro/plugin and parse-tree shape can break or silently change when the host Swift version and `swift-syntax` major diverge.
2. **Xcode / CLI tools update** — `xcode-select` or Xcode upgrades change `swift --version` without a repo change; CI must fail clearly when policy is `fail`.
3. **Helper binary stale** — invoking an old `swift-parser-helper` from `PATH` while Python expects a newer `helper_version` / `schema_version`.
4. **Source location shifts** — trivia / view-mode changes across SwiftSyntax releases can move column numbers; golden fixtures should pin helper + syntax versions.

## Build

```bash
cd swift-parser-helper
swift build -c release
# binary: .build/release/swift-parser-helper
```

Or from repo root:

```bash
./scripts/build_parser_helper.sh
```

## Invocation

```bash
.build/release/swift-parser-helper --version
.build/release/swift-parser-helper --repo-root /path/to/repo --input-file-list files.txt
```

Python discovers the helper via `swiftFrontend.helperPath`, then `PATH`, then a well-known relative build path (see `ultra_trace.parser.helper`).
