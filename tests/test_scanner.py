from __future__ import annotations

from pathlib import Path

from ultra_trace.discovery.scanner import (
    DEFAULT_EXCLUDES,
    RipgrepRepositoryScanner,
    path_is_excluded,
)


def _tree(tmp_path: Path) -> None:
    (tmp_path / "Sources").mkdir()
    (tmp_path / "Sources" / "B.swift").write_text("let b = 1\n", encoding="utf-8")
    (tmp_path / "Sources" / "A.swift").write_text("let a = 1\n", encoding="utf-8")
    (tmp_path / "Tests").mkdir()
    (tmp_path / "Tests" / "C.swift").write_text("let c = 1\n", encoding="utf-8")
    for name in ("Pods", "DerivedData", ".build", "Carthage"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "Skip.swift").write_text("let x = 1\n", encoding="utf-8")
    (tmp_path / "readme.md").write_text("# hi\n", encoding="utf-8")


def test_discover_swift_files_deterministic(tmp_path: Path) -> None:
    _tree(tmp_path)
    scanner = RipgrepRepositoryScanner()
    first = [f.relative_path for f in scanner.discover_swift_files(tmp_path)]
    second = [f.relative_path for f in scanner.discover_swift_files(tmp_path)]
    assert first == second
    assert first == ["Sources/A.swift", "Sources/B.swift", "Tests/C.swift"]


def test_default_excludes_drop_vendor_and_build_trees(tmp_path: Path) -> None:
    _tree(tmp_path)
    scanner = RipgrepRepositoryScanner()
    rels = [f.relative_path for f in scanner.discover_swift_files(tmp_path)]
    assert all(not path_is_excluded(rel, DEFAULT_EXCLUDES) for rel in rels)
    assert "Pods/Skip.swift" not in rels
    assert "DerivedData/Skip.swift" not in rels
    assert ".build/Skip.swift" not in rels


def test_include_and_custom_exclude(tmp_path: Path) -> None:
    _tree(tmp_path)
    scanner = RipgrepRepositoryScanner()
    only_sources = scanner.discover_swift_files(tmp_path, include_paths=["Sources"])
    assert [f.relative_path for f in only_sources] == [
        "Sources/A.swift",
        "Sources/B.swift",
    ]
    no_tests = scanner.discover_swift_files(
        tmp_path, exclude_paths=["Tests", *DEFAULT_EXCLUDES]
    )
    assert [f.relative_path for f in no_tests] == [
        "Sources/A.swift",
        "Sources/B.swift",
    ]
