"""List or restore a verified historical source record from PostgreSQL."""

import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.common import get_engine
from sqlalchemy import text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--path", help="Exact archived path as shown by --list")
    parser.add_argument(
        "--output", type=Path, help="New output file; existing files are never overwritten"
    )
    args = parser.parse_args()
    if args.list:
        with get_engine().connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT path,sha256,octet_length(content) FROM db1_regional_archive.source_archive ORDER BY path"
                )
            )
            for path, digest, size in rows:
                print(f"{path}\t{size}\t{digest}")
        return
    if not args.path or args.output is None:
        parser.error("Use --list or provide both --path and --output.")
    with get_engine().connect() as connection:
        row = connection.execute(
            text("SELECT sha256,content FROM db1_regional_archive.source_archive WHERE path=:path"),
            {"path": args.path},
        ).fetchone()
    if row is None:
        parser.error("Archived path not found.")
    content = bytes(row[1])
    if hashlib.sha256(content).hexdigest() != row[0]:
        raise ValueError("Archived content failed its hash check.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as output:
        output.write(content)
    print(f"Restored verified record to {args.output}")


if __name__ == "__main__":
    main()
