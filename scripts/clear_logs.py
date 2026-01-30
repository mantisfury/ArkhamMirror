#!/usr/bin/env python3
"""Clear (truncate) Arkham log files. Run from repo root or with .env for paths."""

import sys
from pathlib import Path


def repo_root() -> Path:
    """Project root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


def log_paths_from_env(root: Path) -> list[Path]:
    """Read log paths from .env if present."""
    paths = []
    env_file = root / ".env"
    if not env_file.exists():
        return paths
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key in ("ARKHAM_LOG_FILE_PATH", "ARKHAM_LOG_ERROR_FILE_PATH") and value:
            p = root / value
            if p not in paths:
                paths.append(p)
    return paths


def main() -> int:
    root = repo_root()
    seen: set[Path] = set()
    candidates: list[Path] = []

    for p in log_paths_from_env(root):
        r = p.resolve()
        if r not in seen:
            seen.add(r)
            candidates.append(p)

    defaults = [
        root / "data_silo" / "logs" / "arkham.log",
        root / "data_silo" / "logs" / "errors.log",
        root / "logs" / "arkham.log",
        root / "logs" / "errors.log",
    ]
    for p in defaults:
        r = p.resolve()
        if r not in seen:
            seen.add(r)
            candidates.append(p)

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(root))
        except ValueError:
            return str(p)

    cleared = 0
    for path in candidates:
        if path.exists():
            size = path.stat().st_size
            path.write_text("")
            print(f"Cleared {_rel(path)} ({size:,} bytes)")
            cleared += 1

    if not cleared:
        print("No log files found to clear.", file=sys.stderr)
        print("Checked:", " ".join(_rel(p) for p in candidates), file=sys.stderr)
        return 1
    print(f"Done. Cleared {cleared} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
