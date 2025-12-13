#!/usr/bin/env python3
"""
Phase 2.6: Update all imports from old package paths to new consolidated paths.

Replacements:
- arkham_mirror.backend.db.models -> arkham.services.db.models
- arkham_mirror.backend.workers -> arkham.services.workers
- arkham_mirror.backend.utils -> arkham.services.utils
- arkham_mirror.backend -> arkham.services
- arkham_reflex.arkham_reflex.services -> arkham.services
- arkham_reflex.arkham_reflex.components -> arkham.components
- arkham_reflex.arkham_reflex.state -> arkham.state
- arkham_reflex.arkham_reflex.pages -> arkham.pages
- arkham_reflex.arkham_reflex.utils -> arkham.utils
- arkham_reflex.arkham_reflex.models -> arkham.models
- arkham_reflex.arkham_reflex -> arkham
"""

import os
import re
from pathlib import Path

# Order matters - more specific patterns first
REPLACEMENTS = [
    # arkham_mirror patterns (specific to general)
    ("arkham_mirror.backend.db.models", "arkham.services.db.models"),
    ("arkham_mirror.backend.db.vector_store", "arkham.services.db.vector_store"),
    ("arkham_mirror.backend.db", "arkham.services.db"),
    ("arkham_mirror.backend.workers", "arkham.services.workers"),
    (
        "arkham_mirror.backend.utils.security_utils",
        "arkham.services.utils.security_utils",
    ),
    ("arkham_mirror.backend.utils", "arkham.services.utils"),
    ("arkham_mirror.backend.embedding_providers.bge_m3", "arkham.services.db.bge_m3"),
    (
        "arkham_mirror.backend.embedding_providers.minilm_bm25",
        "arkham.services.db.minilm_bm25",
    ),
    ("arkham_mirror.backend.embedding_providers", "arkham.services.db"),
    ("arkham_mirror.backend.embedding_services", "arkham.services.embedding_services"),
    ("arkham_mirror.backend.config", "arkham.services.config"),
    ("arkham_mirror.backend.geocoding_service", "arkham.services.geocoding_service"),
    ("arkham_mirror.backend.retry_utils", "arkham.services.retry_utils"),
    ("arkham_mirror.backend", "arkham.services"),
    # arkham_reflex.arkham_reflex patterns (double-nested, specific to general)
    ("arkham_reflex.arkham_reflex.services.db.models", "arkham.services.db.models"),
    ("arkham_reflex.arkham_reflex.services.db", "arkham.services.db"),
    ("arkham_reflex.arkham_reflex.services.workers", "arkham.services.workers"),
    ("arkham_reflex.arkham_reflex.services.utils", "arkham.services.utils"),
    ("arkham_reflex.arkham_reflex.services", "arkham.services"),
    ("arkham_reflex.arkham_reflex.components", "arkham.components"),
    ("arkham_reflex.arkham_reflex.state", "arkham.state"),
    ("arkham_reflex.arkham_reflex.pages", "arkham.pages"),
    ("arkham_reflex.arkham_reflex.utils", "arkham.utils"),
    ("arkham_reflex.arkham_reflex.models", "arkham.models"),
    ("arkham_reflex.arkham_reflex", "arkham"),
    # arkham_reflex patterns (single-nested - the more common form in state files)
    ("arkham_reflex.services.db.models", "arkham.services.db.models"),
    ("arkham_reflex.services.db", "arkham.services.db"),
    ("arkham_reflex.services.workers", "arkham.services.workers"),
    ("arkham_reflex.services.utils", "arkham.services.utils"),
    ("arkham_reflex.services", "arkham.services"),
    ("arkham_reflex.components", "arkham.components"),
    ("arkham_reflex.state", "arkham.state"),
    ("arkham_reflex.pages", "arkham.pages"),
    ("arkham_reflex.utils", "arkham.utils"),
    ("arkham_reflex.models", "arkham.models"),
    ("arkham_reflex", "arkham"),
    # Path references
    ("arkham_reflex/", "app/"),
]


def update_file(filepath: Path) -> tuple[bool, int]:
    """Update imports in a single file. Returns (changed, num_replacements)."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, 0

    original = content
    total_replacements = 0

    for old, new in REPLACEMENTS:
        count = content.count(old)
        if count > 0:
            content = content.replace(old, new)
            total_replacements += count

    if content != original:
        filepath.write_text(content, encoding="utf-8")
        return True, total_replacements

    return False, 0


def main():
    app_dir = Path(__file__).parent / "arkham"

    if not app_dir.exists():
        print(f"Error: {app_dir} does not exist")
        return

    print("Phase 2.6: Updating imports...")
    print("=" * 60)

    changed_files = []
    total_replacements = 0

    for py_file in app_dir.rglob("*.py"):
        changed, count = update_file(py_file)
        if changed:
            rel_path = py_file.relative_to(app_dir.parent)
            changed_files.append((str(rel_path), count))
            total_replacements += count

    # Also update rxconfig.py and start_app.py in app/
    for extra in ["rxconfig.py", "start_app.py"]:
        extra_path = app_dir.parent / extra
        if extra_path.exists():
            changed, count = update_file(extra_path)
            if changed:
                changed_files.append((extra, count))
                total_replacements += count

    print(
        f"\n✅ Updated {len(changed_files)} files with {total_replacements} replacements:\n"
    )
    for filepath, count in sorted(changed_files):
        print(f"  {filepath}: {count} replacements")

    print("\n" + "=" * 60)
    print("Done! Run 'git diff' to review changes.")


if __name__ == "__main__":
    main()
