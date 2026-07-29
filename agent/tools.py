"""
Read/write primitives the agent uses to explore and modify a target repo.
Kept dependency-free and side-effect-obvious: every function takes the repo
root explicitly so the agent can never accidentally touch files outside it.
"""
import os
import re

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}
MAX_READ_CHARS = 20_000   # keep individual file reads bounded
MAX_GREP_HITS = 200


def _safe_join(root: str, rel_path: str) -> str:
    """Resolve rel_path under root and refuse to escape it (no ../../etc)."""
    full = os.path.normpath(os.path.join(root, rel_path))
    root_abs = os.path.abspath(root)
    if not os.path.abspath(full).startswith(root_abs):
        raise ValueError(f"path escapes repo root: {rel_path}")
    return full


def list_files(root: str) -> list[str]:
    """Return every file path (relative to root), skipping noise dirs."""
    paths = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            paths.append(os.path.relpath(full, root))
    return sorted(paths)


def read_file(root: str, rel_path: str) -> str:
    full = _safe_join(root, rel_path)
    with open(full, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    if len(content) > MAX_READ_CHARS:
        content = content[:MAX_READ_CHARS] + "\n...[truncated]"
    return content


def write_file(root: str, rel_path: str, content: str) -> str:
    full = _safe_join(root, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    return f"wrote {rel_path} ({len(content)} bytes)"


def grep(root: str, pattern: str) -> list[str]:
    """Search all files for a regex; return 'path:line: text' hits."""
    hits = []
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return [f"ERROR: bad regex: {e}"]

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if regex.search(line):
                            rel = os.path.relpath(full, root)
                            hits.append(f"{rel}:{lineno}: {line.strip()}")
                            if len(hits) >= MAX_GREP_HITS:
                                return hits
            except (UnicodeDecodeError, IsADirectoryError, PermissionError):
                continue
    return hits
