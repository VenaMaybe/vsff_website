"""Pre-upgrade SQLite backup without importing the app or applying migrations.

Run as vsff, with the runtime root as the only argument. No environment secrets
are needed. The default app's backup CLI imports the factory before it runs,
so it cannot serve as a before-migration backup of newly checked out code.
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
from uuid import uuid4


def backup_before_upgrade(data_dir):
    root = Path(data_dir).resolve()
    database = root / "pdf_review.sqlite3"
    if not database.exists():
        return None  # Deliberate first startup; never create an empty source DB.
    backups = root / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".pre-upgrade-", suffix=".tmp", dir=backups)
    os.close(descriptor)
    temporary = Path(temporary)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = backups / f"pre-upgrade-{stamp}-{uuid4().hex}.sqlite3"
    try:
        # mode=ro reads the live WAL consistently, unlike immutable=1 or raw copy.
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=30)) as source:
            with closing(sqlite3.connect(temporary)) as target:
                source.backup(target)
                if target.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise RuntimeError("SQLite backup integrity check failed")
        temporary.replace(destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_dir", type=Path)
    arguments = parser.parse_args()
    try:
        result = backup_before_upgrade(arguments.data_dir)
    except Exception:
        raise SystemExit("Review backup failed; refusing deployment. Inspect runtime storage privately.") from None
    print("Review pre-upgrade SQLite snapshot saved." if result else "No review database yet; first startup.")


if __name__ == "__main__":
    main()
