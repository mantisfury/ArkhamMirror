#!/usr/bin/env python
"""
Data Silo Migration Script

One-time migration of existing user data to the new DataSilo structure.
This script moves files from old scattered locations to the centralized DataSilo.

Usage:
    python scripts/migrate_to_data_silo.py          # Dry run (preview only)
    python scripts/migrate_to_data_silo.py --execute  # Actually move files
"""

import os
import sys
import shutil
import argparse
from pathlib import Path

# Add project root for central config
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import (
    PROJECT_ROOT,
    DATA_SILO_PATH,
    DOCUMENTS_DIR,
    PAGES_DIR,
    TEMP_DIR,
    LOGS_DIR,
)

# Old locations (pre-DataSilo)
OLD_LOCATIONS = [
    {
        "name": "Documents (arkham_mirror/data/documents)",
        "source": PROJECT_ROOT / "arkham_mirror" / "data" / "documents",
        "destination": DOCUMENTS_DIR,
    },
    {
        "name": "Page Images (arkham_mirror/data/raw_pdf_pages)",
        "source": PROJECT_ROOT / "arkham_mirror" / "data" / "raw_pdf_pages",
        "destination": PAGES_DIR,
    },
    {
        "name": "Temp Files (arkham_mirror/temp)",
        "source": PROJECT_ROOT / "arkham_mirror" / "temp",
        "destination": TEMP_DIR,
    },
    {
        "name": "Logs (arkham_reflex/logs)",
        "source": PROJECT_ROOT / "arkham_reflex" / "logs",
        "destination": LOGS_DIR,
    },
]


def count_files_in_dir(path: Path) -> tuple[int, int]:
    """Count files and total size in a directory (recursive)."""
    if not path.exists():
        return 0, 0

    file_count = 0
    total_size = 0

    for item in path.rglob("*"):
        if item.is_file():
            file_count += 1
            try:
                total_size += item.stat().st_size
            except OSError:
                pass

    return file_count, total_size


def format_size(bytes_size: int) -> str:
    """Format bytes to human readable."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"


def migrate_location(source: Path, destination: Path, dry_run: bool = True) -> dict:
    """Migrate files from source to destination."""
    result = {
        "files_moved": 0,
        "bytes_moved": 0,
        "errors": [],
    }

    if not source.exists():
        return result

    # Ensure destination exists
    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)

    # Move each item
    for item in source.iterdir():
        dest_path = destination / item.name

        if item.is_file():
            size = item.stat().st_size
            if dry_run:
                print(f"    [DRY RUN] Would move: {item.name} ({format_size(size)})")
            else:
                try:
                    # Check if destination exists
                    if dest_path.exists():
                        print(f"    [SKIP] Already exists: {item.name}")
                        continue

                    shutil.move(str(item), str(dest_path))
                    print(f"    [MOVED] {item.name} ({format_size(size)})")
                    result["files_moved"] += 1
                    result["bytes_moved"] += size
                except Exception as e:
                    result["errors"].append(f"{item.name}: {e}")
                    print(f"    [ERROR] {item.name}: {e}")

        elif item.is_dir():
            # Recursively count files in directory
            file_count, total_size = count_files_in_dir(item)

            if dry_run:
                print(
                    f"    [DRY RUN] Would move directory: {item.name}/ ({file_count} files, {format_size(total_size)})"
                )
            else:
                try:
                    if dest_path.exists():
                        # Merge directories
                        for subitem in item.rglob("*"):
                            if subitem.is_file():
                                relative = subitem.relative_to(item)
                                dest_subpath = dest_path / relative
                                dest_subpath.parent.mkdir(parents=True, exist_ok=True)
                                if not dest_subpath.exists():
                                    shutil.move(str(subitem), str(dest_subpath))
                                    result["files_moved"] += 1
                                    result["bytes_moved"] += subitem.stat().st_size
                        # Remove empty source directory
                        try:
                            shutil.rmtree(str(item))
                        except Exception:
                            pass
                    else:
                        shutil.move(str(item), str(dest_path))
                        result["files_moved"] += file_count
                        result["bytes_moved"] += total_size

                    print(f"    [MOVED] {item.name}/ ({file_count} files)")
                except Exception as e:
                    result["errors"].append(f"{item.name}/: {e}")
                    print(f"    [ERROR] {item.name}/: {e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Migrate data to DataSilo")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually move files (default is dry run)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("DATA SILO MIGRATION")
    print("=" * 80)
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN (preview only)'}")
    print(f"Target: {DATA_SILO_PATH}")
    print("=" * 80)
    print()

    total_files = 0
    total_bytes = 0
    all_errors = []

    for i, location in enumerate(OLD_LOCATIONS, 1):
        print(f"[{i}/{len(OLD_LOCATIONS)}] {location['name']}")
        source = location["source"]
        destination = location["destination"]

        if not source.exists():
            print(f"    Source does not exist: {source}")
            print()
            continue

        file_count, size = count_files_in_dir(source)
        print(f"    Source: {source}")
        print(f"    Destination: {destination}")
        print(f"    Files: {file_count}, Size: {format_size(size)}")
        print()

        result = migrate_location(source, destination, dry_run=not args.execute)
        total_files += result["files_moved"]
        total_bytes += result["bytes_moved"]
        all_errors.extend(result["errors"])
        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if args.execute:
        print(f"Files moved: {total_files}")
        print(f"Data moved: {format_size(total_bytes)}")
        if all_errors:
            print(f"Errors: {len(all_errors)}")
            for err in all_errors:
                print(f"  - {err}")
    else:
        # Preview mode - count what would be moved
        preview_files = 0
        preview_bytes = 0
        for location in OLD_LOCATIONS:
            if location["source"].exists():
                fc, sz = count_files_in_dir(location["source"])
                preview_files += fc
                preview_bytes += sz

        print(f"Files that would be moved: {preview_files}")
        print(f"Data that would be moved: {format_size(preview_bytes)}")
        print()
        print("To actually migrate files, run:")
        print(f"    python {__file__} --execute")

    print("=" * 80)
    print()

    # Verify DataSilo structure
    print("DataSilo Directory Structure:")
    if DATA_SILO_PATH.exists():
        for subdir in DATA_SILO_PATH.iterdir():
            if subdir.is_dir():
                fc, sz = count_files_in_dir(subdir)
                print(f"  {subdir.name}/: {fc} files, {format_size(sz)}")
    else:
        print("  (not created yet)")
    print()


if __name__ == "__main__":
    main()
