"""Production WSGI entrypoint; configuration comes only from the environment."""

import os
from pathlib import Path

from review import PROJECT_ROOT, create_app


if os.environ.get("PDF_REVIEW_ENV") != "production":
    raise RuntimeError("The production entrypoint requires PDF_REVIEW_ENV=production.")

data_dir = Path(os.environ.get("PDF_REVIEW_DATA_DIR", "")).expanduser()
if not data_dir.is_absolute() or data_dir.resolve().is_relative_to(PROJECT_ROOT.parent):
    raise RuntimeError("Production requires an absolute PDF_REVIEW_DATA_DIR outside the repository.")

database = os.environ.get("PDF_REVIEW_DATABASE")
if database:
    database_path = Path(database).expanduser()
    if not database_path.is_absolute() or database_path.resolve().is_relative_to(PROJECT_ROOT.parent):
        raise RuntimeError("PDF_REVIEW_DATABASE must be absolute and outside the repository.")

app = create_app()
