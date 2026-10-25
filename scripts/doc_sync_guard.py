"""Documentation Sync Guard: Enforce that modifying src/ requires updating doc/ or README.md."""

import subprocess
import sys


def get_staged_files() -> list[str]:
    """Get list of staged files from git diff --cached."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def check_doc_sync() -> int:
    """Verify that staged src/ modifications are accompanied by doc/ or README.md changes."""
    staged_files = get_staged_files()

    if not staged_files:
        sys.stdout.write("[DOC-SYNC] Clean: No staged files to verify.\n")
        return 0

    has_src = any(f.startswith("src/") for f in staged_files)
    has_doc = any(f.startswith("doc/") or f == "README.md" for f in staged_files)

    if has_src and not has_doc:
        sys.stderr.write(
            "[CONSTITUTION ERROR] Modifying src/ requires updating doc/ or "
            "README.md in the same commit.\n"
            f"Staged files: {staged_files}\n"
        )
        return 1

    sys.stdout.write("[DOC-SYNC] Clean: Documentation is synchronized.\n")
    return 0


def main() -> None:
    sys.exit(check_doc_sync())


if __name__ == "__main__":
    main()
