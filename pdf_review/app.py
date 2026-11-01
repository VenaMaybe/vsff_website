"""Development entry point for PDF Review."""

from pathlib import Path
import os

from dotenv import load_dotenv

from review import create_app


# Explicit process variables take precedence over ignored local configuration.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
app = create_app()


if __name__ == "__main__":
    app.extensions["socketio"].run(
        app, host=os.environ.get("PDF_REVIEW_HOST", "127.0.0.1"),
        port=int(os.environ.get("PDF_REVIEW_PORT", "5000")), allow_unsafe_werkzeug=True
    )
