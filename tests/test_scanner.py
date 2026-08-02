from __future__ import annotations

from pathlib import Path

from ultra_trace.discovery.scanner import RipgrepRepositoryScanner


def test_discover_swift_files_deterministic(tmp_path: Path) -> None:
    (tmp_path / "Sources").mkdir()
    (tmp_path / "Sources" / "B.swift").write_text("let b = 1\n", encoding="utf-8")
    (tmp_path / "Sources" / "A.swift").write_text("let a = 1\n", encoding="utf-8")
    (tmp_path / "Pods").mkdir()
    (tmp_path / "Pods" / "Skip.swift").write_text("let x = 1\n", encoding="utf-8")
    (tmp_path / "readme.md").write_text("# hi\n", encoding="utf-8")

    scanner = RipgrepRepositoryScanner()
    files = scanner.discover_swift_files(tmp_path)
    rels = [f.relative_path for f in files]
    assert rels == ["Sources/A.swift", "Sources/B.swift"]
