#!/usr/bin/env python3
"""
Run SQL migrations in ./migrations (idempotent runner).

Features:
- Enumerates migrations directory (migrations/*.sql) so you can add more later
- Records applied migrations in a DB table (filename + checksum)
- Applies new migrations in lexical order (e.g. 001_, 002_, 003_)
- Handles migrations that include their own BEGIN/COMMIT blocks

Usage:
  python scripts/run_migrations.py --list
  python scripts/run_migrations.py
  python scripts/run_migrations.py --dry-run

Database:
  Uses DATABASE_URL from env, or defaults to:
    postgresql://arkham:arkhampass@localhost:5432/arkhamdb
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


def _load_env() -> None:
    env_file = ROOT / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
        except ImportError:
            # Optional; runner still works if env vars are already set
            return
        load_dotenv(env_file)


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql://arkham:arkhampass@localhost:5432/arkhamdb")
    # psycopg2 doesn't understand the SQLAlchemy async scheme prefix
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


@dataclass(frozen=True)
class Migration:
    filename: str
    path: Path
    checksum_sha256: str
    sql: str


_TXN_MARKER_RE = re.compile(r"(?im)^[ \t]*(BEGIN|COMMIT|ROLLBACK)\b")


def _read_migrations() -> list[Migration]:
    if not MIGRATIONS_DIR.exists():
        raise RuntimeError(f"Migrations directory not found: {MIGRATIONS_DIR}")

    paths = sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name)
    migrations: list[Migration] = []
    for p in paths:
        sql = p.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        migrations.append(Migration(filename=p.name, path=p, checksum_sha256=checksum, sql=sql))
    return migrations


def _has_explicit_transaction(sql: str) -> bool:
    # If a migration includes its own BEGIN/COMMIT, we should not wrap it.
    return bool(_TXN_MARKER_RE.search(sql))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SQL migrations from ./migrations")
    parser.add_argument("--list", action="store_true", help="List discovered migrations and exit")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run, but do not execute")
    parser.add_argument(
        "--table",
        default="arkham_frame.schema_migrations",
        help="Migration tracking table (default: arkham_frame.schema_migrations)",
    )
    args = parser.parse_args()

    _load_env()
    database_url = _get_database_url()

    try:
        import psycopg2
    except ImportError:
        print("Install psycopg2: pip install psycopg2-binary", file=sys.stderr)
        return 1

    migrations = _read_migrations()
    if args.list:
        for m in migrations:
            print(f"{m.filename}  sha256={m.checksum_sha256[:12]}  explicit_txn={_has_explicit_transaction(m.sql)}")
        return 0

    if not migrations:
        print("No migrations found.")
        return 0

    # Split schema/table
    if "." not in args.table:
        print("--table must be schema-qualified, e.g. arkham_frame.schema_migrations", file=sys.stderr)
        return 2
    schema_name, table_name = args.table.split(".", 1)

    # Hard safety: avoid SQL injection via --table. Keep it simple/strict.
    ident_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    if not ident_re.match(schema_name) or not ident_re.match(table_name):
        print("--table must be simple identifiers like arkham_frame.schema_migrations", file=sys.stderr)
        return 2

    conn = psycopg2.connect(database_url)
    try:
        def ensure_not_in_transaction() -> None:
            """
            psycopg2 cannot change autocommit inside a transaction.
            Always rollback to clear any implicit transaction state.
            """
            try:
                conn.rollback()
            except Exception:
                pass

        with conn.cursor() as cur:
            # Ensure schema + tracking table exist
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} (
                    filename TEXT PRIMARY KEY,
                    checksum_sha256 TEXT NOT NULL,
                    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

            cur.execute(f"SELECT filename, checksum_sha256 FROM {schema_name}.{table_name}")
            applied = {row[0]: row[1] for row in cur.fetchall()}

        pending: list[Migration] = []
        for m in migrations:
            if m.filename not in applied:
                pending.append(m)
                continue
            if applied[m.filename] != m.checksum_sha256:
                raise RuntimeError(
                    f"Migration checksum mismatch for {m.filename}.\n"
                    f"DB:   {applied[m.filename]}\n"
                    f"File: {m.checksum_sha256}\n"
                    "Refusing to continue (migrations should be immutable once applied)."
                )

        if not pending:
            print("All migrations already applied.")
            return 0

        print(f"Database: {database_url}")
        print(f"Tracking: {schema_name}.{table_name}")
        print(f"Pending migrations: {len(pending)}")

        if args.dry_run:
            for m in pending:
                print(f"[DRY RUN] Would apply {m.filename}")
            return 0

        for m in pending:
            explicit_txn = _has_explicit_transaction(m.sql)
            applied_at = datetime.now(timezone.utc).isoformat()

            print(f"Applying {m.filename} (explicit_txn={explicit_txn}) ...")

            if explicit_txn:
                # Let the migration manage its own BEGIN/COMMIT if it wants to.
                ensure_not_in_transaction()
                conn.autocommit = True
                try:
                    with conn.cursor() as cur:
                        cur.execute(m.sql)
                        cur.execute(
                            f"INSERT INTO {schema_name}.{table_name} (filename, checksum_sha256, applied_at) VALUES (%s, %s, %s)",
                            (m.filename, m.checksum_sha256, applied_at),
                        )
                finally:
                    ensure_not_in_transaction()
                    conn.autocommit = False
            else:
                ensure_not_in_transaction()
                conn.autocommit = False
                with conn.cursor() as cur:
                    cur.execute(m.sql)
                    cur.execute(
                        f"INSERT INTO {schema_name}.{table_name} (filename, checksum_sha256, applied_at) VALUES (%s, %s, %s)",
                        (m.filename, m.checksum_sha256, applied_at),
                    )
                conn.commit()

        print("Migrations complete.")
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

