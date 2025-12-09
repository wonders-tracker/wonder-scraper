#!/usr/bin/env python3
"""
Import contributor data dump into local PostgreSQL.

This script imports the safe database export for local development.
It expects data exported by export_contributor_data.py.

Usage:
    python scripts/import_contributor_data.py data/exports/wonder_data_20241201.sql.gz
    python scripts/import_contributor_data.py data/exports/wonder_data_20241201.tar.gz

Prerequisites:
    - Local PostgreSQL running (use docker-compose.dev.yml)
    - DATABASE_URL set in .env
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def get_database_url():
    """Get database URL from environment."""
    from dotenv import load_dotenv
    load_dotenv()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set in environment")
        print("Hint: Copy .env.example to .env and configure DATABASE_URL")
        sys.exit(1)
    return url


def parse_database_url(url: str) -> dict:
    """Parse PostgreSQL connection URL into components."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/"),
        "user": parsed.username,
        "password": parsed.password,
    }


def check_database_connection(db_config: dict) -> bool:
    """Verify database is accessible."""
    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["password"]

    cmd = [
        "psql",
        "-h", db_config["host"],
        "-p", str(db_config["port"]),
        "-U", db_config["user"],
        "-d", db_config["database"],
        "-c", "SELECT 1",
    ]

    result = subprocess.run(cmd, env=env, capture_output=True)
    return result.returncode == 0


def import_sql(sql_file: Path, db_config: dict, reset: bool = False):
    """Import SQL dump file."""
    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["password"]

    # Decompress if needed
    if sql_file.suffix == ".gz":
        print(f"Decompressing {sql_file.name}...")
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        subprocess.run(["gunzip", "-c", str(sql_file)], stdout=open(tmp_path, "w"), check=True)
        sql_file = tmp_path
        cleanup_file = True
    else:
        cleanup_file = False

    try:
        if reset:
            print("Resetting database tables...")
            # The SQL dump includes DROP IF EXISTS, so this is handled

        print(f"Importing data from {sql_file.name}...")
        cmd = [
            "psql",
            "-h", db_config["host"],
            "-p", str(db_config["port"]),
            "-U", db_config["user"],
            "-d", db_config["database"],
            "-f", str(sql_file),
            "-v", "ON_ERROR_STOP=1",
        ]

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"ERROR: Import failed")
            print(result.stderr)
            sys.exit(1)

        # Count lines that say "INSERT" or "COPY" for progress
        print("Import completed successfully!")

    finally:
        if cleanup_file:
            tmp_path.unlink()


def import_csv(archive_file: Path, db_config: dict, reset: bool = False):
    """Import CSV archive."""
    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["password"]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Extract archive
        print(f"Extracting {archive_file.name}...")
        subprocess.run(
            ["tar", "-xzf", str(archive_file), "-C", str(tmpdir)],
            check=True
        )

        # Find extracted directory
        csv_dirs = list(tmpdir.glob("wonder_data_*"))
        if not csv_dirs:
            print("ERROR: No data directory found in archive")
            sys.exit(1)
        csv_dir = csv_dirs[0]

        # Import each CSV file
        csv_files = list(csv_dir.glob("*.csv"))
        print(f"Found {len(csv_files)} CSV files to import")

        for csv_file in csv_files:
            table_name = csv_file.stem

            if reset:
                # Truncate table before import
                truncate_cmd = [
                    "psql",
                    "-h", db_config["host"],
                    "-p", str(db_config["port"]),
                    "-U", db_config["user"],
                    "-d", db_config["database"],
                    "-c", f"TRUNCATE {table_name} CASCADE",
                ]
                subprocess.run(truncate_cmd, env=env, capture_output=True)

            # Import CSV
            copy_cmd = f"\\COPY {table_name} FROM STDIN WITH CSV HEADER"
            cmd = [
                "psql",
                "-h", db_config["host"],
                "-p", str(db_config["port"]),
                "-U", db_config["user"],
                "-d", db_config["database"],
                "-c", copy_cmd,
            ]

            with open(csv_file, "r") as f:
                result = subprocess.run(cmd, env=env, stdin=f, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"  WARNING: Failed to import {table_name}: {result.stderr}")
            else:
                rows = sum(1 for _ in open(csv_file)) - 1
                print(f"  {table_name}: {rows:,} rows imported")

    print("Import completed!")


def run_migrations(db_config: dict):
    """Run Alembic migrations to ensure schema is up to date."""
    print("Running database migrations...")
    result = subprocess.run(
        ["poetry", "run", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"WARNING: Migration failed: {result.stderr}")
        print("You may need to run migrations manually: poetry run alembic upgrade head")
    else:
        print("Migrations applied successfully")


def main():
    parser = argparse.ArgumentParser(
        description="Import contributor data dump into local PostgreSQL"
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Data file to import (.sql.gz or .tar.gz)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset (truncate) tables before import"
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip running Alembic migrations"
    )

    args = parser.parse_args()

    if not args.file.exists():
        print(f"ERROR: File not found: {args.file}")
        sys.exit(1)

    # Get database config
    db_url = get_database_url()
    db_config = parse_database_url(db_url)

    # Check connection
    print(f"Connecting to database at {db_config['host']}:{db_config['port']}...")
    if not check_database_connection(db_config):
        print("ERROR: Cannot connect to database")
        print("Hint: Is PostgreSQL running? Try: docker-compose -f docker-compose.dev.yml up -d")
        sys.exit(1)
    print("Connected!")

    # Run migrations first
    if not args.skip_migrations:
        run_migrations(db_config)

    # Import based on file type
    if args.file.name.endswith(".sql.gz") or args.file.name.endswith(".sql"):
        import_sql(args.file, db_config, args.reset)
    elif args.file.name.endswith(".tar.gz"):
        import_csv(args.file, db_config, args.reset)
    else:
        print(f"ERROR: Unknown file format: {args.file.suffix}")
        print("Expected: .sql.gz or .tar.gz")
        sys.exit(1)

    print("\nData import complete!")
    print("You can now run the application: poetry run uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
