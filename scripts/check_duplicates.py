"""Lightweight, zero-dependency token-block duplicate code detector for Python source files."""

import sys
from collections import defaultdict
from pathlib import Path


def extract_normalized_blocks(file_path: Path, block_size: int = 5) -> dict[str, list[int]]:
    """Extract line-block hashes ignoring comments and blank lines."""
    blocks: dict[str, list[int]] = defaultdict(list)
    try:
        lines = [
            line.strip()
            for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    except OSError:
        return blocks

    for i in range(len(lines) - block_size + 1):
        block_text = "\n".join(lines[i : i + block_size])
        blocks[block_text].append(i + 1)
    return blocks


def check_directory(src_dir: Path, block_size: int = 5) -> int:
    """Check for duplicate blocks across all python files in target directory."""
    global_blocks: dict[str, list[str]] = defaultdict(list)
    py_files = sorted(src_dir.rglob("*.py"))

    for py_file in py_files:
        file_blocks = extract_normalized_blocks(py_file, block_size)
        for block_text, line_nos in file_blocks.items():
            for line_no in line_nos:
                global_blocks[block_text].append(f"{py_file.name}:{line_no}")

    duplicates_found = 0
    for block_text, occurrences in global_blocks.items():
        if len(occurrences) > 1:
            first_preview = block_text.splitlines()[0]
            sys.stderr.write(
                f"[DUP-CHECK ERROR] Duplicate block ({block_size} lines) found in: "
                f"{', '.join(occurrences)} (Preview: {first_preview})\n"
            )
            duplicates_found += 1

    if duplicates_found > 0:
        sys.stderr.write(f"[DUP-CHECK] Failed: {duplicates_found} duplicate blocks detected.\n")
        return 1

    sys.stdout.write(f"[DUP-CHECK] Clean: Verified {len(py_files)} files without duplicates.\n")
    return 0


def main() -> None:
    src_path = Path("src")
    if not src_path.exists():
        sys.stdout.write("[DUP-CHECK] Skipped: src/ directory does not exist.\n")
        sys.exit(0)
    sys.exit(check_directory(src_path))


if __name__ == "__main__":
    main()
