"""
Prune non-runtime files from the packaged embedded Python environment.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


REMOVE_DIR_NAMES = {
    "__pycache__",
    "test",
    "tests",
    "testing",
    "bench",
    "benches",
    "benchmark",
    "benchmarks",
    "example",
    "examples",
    "doc",
    "docs",
}

REMOVE_FILE_SUFFIXES = {".pyc", ".pyo"}
REMOVE_FILE_NAMES = {
    "conftest.py",
}


def _should_remove_dir(path: Path) -> bool:
    return path.name.lower() in REMOVE_DIR_NAMES


def _should_remove_file(path: Path) -> bool:
    return path.suffix.lower() in REMOVE_FILE_SUFFIXES or path.name in REMOVE_FILE_NAMES


def _iter_targets(root: Path) -> tuple[list[Path], list[Path]]:
    dirs: list[Path] = []
    files: list[Path] = []

    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_dir() and _should_remove_dir(path):
            dirs.append(path)
        elif path.is_file() and _should_remove_file(path):
            files.append(path)

    dirs.sort(key=lambda item: len(item.parts), reverse=True)
    files.sort(key=lambda item: len(item.parts), reverse=True)
    return dirs, files


def _tree_size(root: Path) -> int:
    total = 0
    for child in root.rglob("*"):
        if child.is_file() and not child.is_symlink():
            total += child.stat().st_size
    return total


def prune(root: Path) -> tuple[int, int, int]:
    dirs, files = _iter_targets(root)
    removed_dirs = 0
    removed_files = 0
    before_bytes = _tree_size(root)

    for path in files:
        if not path.exists():
            continue
        path.unlink()
        removed_files += 1

    for path in dirs:
        if not path.exists():
            continue
        shutil.rmtree(path, ignore_errors=True)
        removed_dirs += 1

    after_bytes = _tree_size(root)
    reclaimed_bytes = max(0, before_bytes - after_bytes)
    return removed_dirs, removed_files, reclaimed_bytes


def main() -> int:
    default_root = Path(__file__).resolve().parents[1] / "frontend" / "resources" / "python"
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else default_root

    if not root.exists():
        print(f"[prune] target does not exist: {root}", file=sys.stderr)
        return 1

    dirs, files, reclaimed = prune(root)
    print(
        f"[prune] removed {dirs} directories and {files} files, "
        f"reclaimed {reclaimed / (1024 * 1024):.2f} MB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
