"""Offline SQLite backups; immutable blobs are retained separately."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

import click

from .database import connect


def init_backup_cli(app):
    @app.cli.command("backup-database")
    def backup_database():
        """Create a consistent SQLite snapshot in the runtime backups directory."""
        directory = Path(app.config["BACKUP_DIR"])
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = directory / f"pdf-review-{stamp}-{uuid4().hex}.sqlite3"
        source = connect(app.config["DATABASE"])
        try:
            destination = sqlite3.connect(path)
            try:
                source.backup(destination)
            finally:
                destination.close()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            source.close()
        click.echo(f"SQLite backup created: {path}")
