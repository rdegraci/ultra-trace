from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDES: tuple[str, ...] = (
    ".git",
    "DerivedData",
    ".build",
    "Pods",
    "Carthage",
    "SourcePackages",
)


def path_is_excluded(relative_path: str, excludes: Sequence[str]) -> bool:
    """True when *relative_path* matches a default or configured exclude token."""
    rel = relative_path.replace("\\", "/").lstrip("./")
    parts = rel.split("/")
    for raw in excludes:
        token = raw.strip().replace("\\", "/").strip("/")
        if not token:
            continue
        if rel == token or rel.startswith(token + "/"):
            return True
        if token in parts:
            return True
    return False


@dataclass(frozen=True)
class RepositoryFile:
    path: Path
    relative_path: str


class RepositoryScanner(Protocol):
    def discover_swift_files(
        self,
        repo_root: Path,
        *,
        include_paths: Sequence[str] = (),
        exclude_paths: Sequence[str] = (),
    ) -> list[RepositoryFile]: ...


class RipgrepRepositoryScanner:
    """Discover Swift files using python-ripgrep when available, else system rg."""

    def discover_swift_files(
        self,
        repo_root: Path,
        *,
        include_paths: Sequence[str] = (),
        exclude_paths: Sequence[str] = (),
    ) -> list[RepositoryFile]:
        root = repo_root.resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Repository root does not exist: {root}")

        excludes = tuple(exclude_paths) if exclude_paths else DEFAULT_EXCLUDES
        paths = self._search(root, include_paths=include_paths, exclude_paths=excludes)
        files = [
            RepositoryFile(path=p, relative_path=p.relative_to(root).as_posix())
            for p in paths
            if p.suffix == ".swift" and p.is_file()
        ]
        files = [
            item for item in files if not path_is_excluded(item.relative_path, excludes)
        ]
        files.sort(key=lambda f: f.relative_path)
        return files

    def _search(
        self,
        root: Path,
        *,
        include_paths: Sequence[str],
        exclude_paths: Sequence[str],
    ) -> list[Path]:
        try:
            return self._search_python_ripgrep(
                root, include_paths=include_paths, exclude_paths=exclude_paths
            )
        except Exception as exc:  # noqa: BLE001 — fall back intentionally
            logger.debug("python-ripgrep unavailable or failed (%s); using rg CLI", exc)
        try:
            return self._search_rg_cli(
                root, include_paths=include_paths, exclude_paths=exclude_paths
            )
        except FileNotFoundError as exc:
            logger.debug("rg CLI unavailable (%s); walking filesystem", exc)
            return self._search_walk(
                root, include_paths=include_paths, exclude_paths=exclude_paths
            )

    def _search_python_ripgrep(
        self,
        root: Path,
        *,
        include_paths: Sequence[str],
        exclude_paths: Sequence[str],
    ) -> list[Path]:
        # python-ripgrep exposes a low-level API that varies by version; keep
        # discovery behind this method so Slice 1 stays unblocked.
        import ripgrep  # type: ignore[import-not-found]

        search_roots = [root / p for p in include_paths] if include_paths else [root]
        found: set[Path] = set()
        for search_root in search_roots:
            if not search_root.exists():
                continue
            # Prefer file listing helpers if present; otherwise raise to CLI fallback.
            if hasattr(ripgrep, "search"):
                search_fn = getattr(ripgrep, "search")
                result = search_fn(
                    pattern=".",
                    path=str(search_root),
                    glob="*.swift",
                    files=True,
                )
                for item in result:
                    found.add(Path(str(item)))
            else:
                raise RuntimeError("python-ripgrep API not usable for file listing")
        return sorted(found)

    def _search_rg_cli(
        self,
        root: Path,
        *,
        include_paths: Sequence[str],
        exclude_paths: Sequence[str],
    ) -> list[Path]:
        search_roots = (
            [str(root / p) for p in include_paths] if include_paths else [str(root)]
        )
        cmd: list[str] = [
            "rg",
            "--files",
            "--glob",
            "*.swift",
            "--hidden",
            "--no-messages",
        ]
        for excl in exclude_paths:
            cmd.extend(["--glob", f"!{excl}", "--glob", f"!{excl}/**"])
        cmd.extend(search_roots)

        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode not in (0, 1):
            raise RuntimeError(
                f"rg failed (exit {proc.returncode}): {proc.stderr.strip()}"
            )
        paths: list[Path] = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            path = Path(line)
            if not path.is_absolute():
                path = (root / path).resolve()
            paths.append(path)
        return paths

    def _search_walk(
        self,
        root: Path,
        *,
        include_paths: Sequence[str],
        exclude_paths: Sequence[str],
    ) -> list[Path]:
        search_roots = [root / p for p in include_paths] if include_paths else [root]
        found: list[Path] = []
        for search_root in search_roots:
            if not search_root.exists():
                continue
            if search_root.is_file():
                if search_root.suffix == ".swift":
                    found.append(search_root.resolve())
                continue
            for dirpath, dirnames, filenames in os.walk(search_root):
                current = Path(dirpath)
                try:
                    rel_dir = current.relative_to(root).as_posix()
                except ValueError:
                    rel_dir = current.name
                dirnames[:] = [
                    name
                    for name in dirnames
                    if not path_is_excluded(
                        f"{rel_dir}/{name}" if rel_dir != "." else name,
                        exclude_paths,
                    )
                ]
                for name in filenames:
                    if name.endswith(".swift"):
                        found.append((current / name).resolve())
        return found


def default_scanner() -> RipgrepRepositoryScanner:
    return RipgrepRepositoryScanner()
