#!/usr/bin/env python3
"""
Export safe database tables for contributors.

This script exports public market data that can be shared with OSS contributors.
Sensitive tables (users, portfolios, api_keys, etc.) are explicitly excluded.

Usage:
    python scripts/export_contributor_data.py --output data/exports/
    python scripts/export_contributor_data.py --output data/exports/ --format sql
    python scripts/export_contributor_data.py --output data/exports/ --format csv
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Tables SAFE to export (public market data)
SAFE_TABLES = [
    "rarity",
    "card",
    "marketprice",
    "marketsnapshot",
    "blokpax_storefront",
    "blokpax_snapshot",
    "blokpax_sale",
    "blokpax_asset",
    "blokpax_offer",
    "listing_report",  # Reported listings (no user PII)
]

# Tables explicitly EXCLUDED (sensitive/user data)
EXCLUDED_TABLES = [
    "user",
    "portfolio_item",
    "portfolio_card",
    "api_key",
    "pageview",
    "card_meta_vote",
    "card_meta_vote_reaction",
    "watchlist",
    "watchlist_item",
    "webhook_event",
    "alembic_version",  # Migration state
]


def get_database_url():
    """Get database URL from environment."""
    from dotenv import load_dotenv
    load_dotenv()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set in environment")
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


def export_sql(output_dir: Path, db_config: dict, tables: list, days: int = None):
    """Export tables as SQL dump."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"wonder_data_{timestamp}.sql"

    # Build pg_dump command
    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["password"]

    cmd = [
        "pg_dump",
        "-h", db_config["host"],
        "-p", str(db_config["port"]),
        "-U", db_config["user"],
        "-d", db_config["database"],
        "--no-owner",
        "--no-acl",
        "--clean",
        "--if-exists",
    ]

    # Add each table
    for table in tables:
        cmd.extend(["-t", table])

    print(f"Exporting {len(tables)} tables to SQL...")
    print(f"Tables: {', '.join(tables)}")

    with open(output_file, "w") as f:
        # Add header comment
        f.write(f"-- WondersTracker Contributor Data Export\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n")
        f.write(f"-- Tables: {', '.join(tables)}\n")
        f.write(f"-- \n")
        f.write(f"-- This export contains public market data only.\n")
        f.write(f"-- No user data, portfolios, or API keys are included.\n")
        f.write(f"-- \n\n")

        result = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.PIPE)

    if result.returncode != 0:
        print(f"ERROR: pg_dump failed: {result.stderr.decode()}")
        sys.exit(1)

    # Compress the output
    compressed_file = output_file.with_suffix(".sql.gz")
    subprocess.run(["gzip", "-f", str(output_file)])

    size_mb = compressed_file.stat().st_size / (1024 * 1024)
    print(f"Exported to: {compressed_file} ({size_mb:.1f} MB)")

    return compressed_file


def export_csv(output_dir: Path, db_config: dict, tables: list, days: int = None):
    """Export tables as CSV files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_dir = output_dir / f"wonder_data_{timestamp}"
    csv_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["password"]

    print(f"Exporting {len(tables)} tables to CSV...")

    for table in tables:
        output_file = csv_dir / f"{table}.csv"

        # Build COPY command
        query = f"\\COPY {table} TO STDOUT WITH CSV HEADER"

        cmd = [
            "psql",
            "-h", db_config["host"],
            "-p", str(db_config["port"]),
            "-U", db_config["user"],
            "-d", db_config["database"],
            "-c", query,
        ]

        with open(output_file, "w") as f:
            result = subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.PIPE)

        if result.returncode != 0:
            print(f"  WARNING: Failed to export {table}: {result.stderr.decode()}")
            continue

        rows = sum(1 for _ in open(output_file)) - 1  # Subtract header
        print(f"  {table}: {rows:,} rows")

    # Create archive
    archive_file = output_dir / f"wonder_data_{timestamp}.tar.gz"
    subprocess.run(
        ["tar", "-czf", str(archive_file), "-C", str(output_dir), csv_dir.name],
        check=True
    )

    # Cleanup uncompressed directory
    subprocess.run(["rm", "-rf", str(csv_dir)])

    size_mb = archive_file.stat().st_size / (1024 * 1024)
    print(f"Exported to: {archive_file} ({size_mb:.1f} MB)")

    return archive_file


def get_table_counts(db_config: dict, tables: list) -> dict:
    """Get row counts for tables."""
    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["password"]

    counts = {}
    for table in tables:
        cmd = [
            "psql",
            "-h", db_config["host"],
            "-p", str(db_config["port"]),
            "-U", db_config["user"],
            "-d", db_config["database"],
            "-t", "-c", f"SELECT COUNT(*) FROM {table}",
        ]

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode == 0:
            counts[table] = int(result.stdout.strip())
        else:
            counts[table] = -1  # Table doesn't exist

    return counts


def main():
    parser = argparse.ArgumentParser(
        description="Export safe database tables for contributors"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("data/exports"),
        help="Output directory (default: data/exports/)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["sql", "csv"],
        default="sql",
        help="Export format (default: sql)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be exported without exporting"
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        help="Specific tables to export (default: all safe tables)"
    )

    args = parser.parse_args()

    # Get database config
    db_url = get_database_url()
    db_config = parse_database_url(db_url)

    # Determine tables to export
    tables = args.tables if args.tables else SAFE_TABLES

    # Validate no sensitive tables are requested
    for table in tables:
        if table in EXCLUDED_TABLES:
            print(f"ERROR: Cannot export sensitive table: {table}")
            sys.exit(1)

    # Get table counts
    print("Checking tables...")
    counts = get_table_counts(db_config, tables)

    # Filter to existing tables
    existing_tables = [t for t in tables if counts.get(t, -1) >= 0]
    missing_tables = [t for t in tables if counts.get(t, -1) < 0]

    if missing_tables:
        print(f"Note: Skipping non-existent tables: {', '.join(missing_tables)}")

    if not existing_tables:
        print("ERROR: No tables to export")
        sys.exit(1)

    # Show summary
    print("\n" + "=" * 50)
    print("EXPORT SUMMARY")
    print("=" * 50)
    total_rows = 0
    for table in existing_tables:
        count = counts[table]
        total_rows += count
        print(f"  {table}: {count:,} rows")
    print("-" * 50)
    print(f"  Total: {total_rows:,} rows in {len(existing_tables)} tables")
    print("=" * 50 + "\n")

    if args.dry_run:
        print("Dry run - no export performed")
        return

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Export
    if args.format == "sql":
        export_sql(args.output, db_config, existing_tables)
    else:
        export_csv(args.output, db_config, existing_tables)

    print("\nDone! Share the export file with contributors via wonder-data repo.")


if __name__ == "__main__":
    main()
