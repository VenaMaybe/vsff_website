"""Immutable content-addressed storage for imported PDFs."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO


BUFFER_SIZE = 1024 * 1024
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class StorageError(RuntimeError):
    """Base class for a controlled blob-storage failure."""


class InvalidPDFError(StorageError):
    """Raised when an uploaded file does not pass basic PDF validation."""


class BlobIntegrityError(StorageError):
    """Raised if bytes do not match their content-addressed identity."""


class MissingBlobError(StorageError):
    """Raised when a recorded blob is absent."""


@dataclass(frozen=True)
class StoredBlob:
    sha256: str
    relative_path: str
    file_size: int
    created: bool


@dataclass(frozen=True)
class IntegrityResult:
    ok: bool
    expected_sha256: str
    actual_sha256: str | None
    expected_size: int
    actual_size: int | None
    message: str


def sha256_file(path: Path | str) -> str:
    """Return the lowercase SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(BUFFER_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BlobStore:
    """Store PDFs by digest without ever replacing existing blob bytes."""

    def __init__(self, storage_root: Path | str):
        self.root = Path(storage_root).resolve()
        self.blob_dir = self.root / "blobs"
        self.blob_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def relative_path(sha256: str) -> str:
        if not SHA256_PATTERN.fullmatch(sha256):
            raise StorageError("Invalid SHA-256 blob identity.")
        return f"blobs/{sha256}.pdf"

    def resolve(self, relative_path: str, expected_sha256: str) -> Path:
        """Resolve only the canonical internal path for an expected digest."""
        canonical = self.relative_path(expected_sha256)
        if PurePosixPath(relative_path).as_posix() != canonical:
            raise StorageError("The recorded blob path is not canonical.")
        return self.root / Path(*PurePosixPath(canonical).parts)

    def ingest(self, source: BinaryIO) -> StoredBlob:
        """Copy, hash, validate, and atomically publish an uploaded PDF."""
        digest = hashlib.sha256()
        size = 0
        prefix = bytearray()
        temp_path: Path | None = None
        try:
            descriptor, temp_name = tempfile.mkstemp(
                prefix=".incoming-", suffix=".pdf", dir=self.blob_dir
            )
            temp_path = Path(temp_name)
            with os.fdopen(descriptor, "wb") as destination:
                while True:
                    chunk = source.read(BUFFER_SIZE)
                    if not chunk:
                        break
                    if len(prefix) < 1024:
                        prefix.extend(chunk[: 1024 - len(prefix)])
                    destination.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                destination.flush()
                os.fsync(destination.fileno())

            if b"%PDF-" not in prefix:
                raise InvalidPDFError("The selected file does not have a PDF header.")

            sha256 = digest.hexdigest()
            relative = self.relative_path(sha256)
            final_path = self.resolve(relative, sha256)
            created = False
            try:
                os.link(temp_path, final_path)
                created = True
            except FileExistsError:
                if sha256_file(final_path) != sha256:
                    raise BlobIntegrityError(
                        "An existing blob does not match its content-addressed filename."
                    )
            except OSError as error:
                if final_path.exists():
                    if sha256_file(final_path) != sha256:
                        raise BlobIntegrityError(
                            "An existing blob does not match its content-addressed filename."
                        ) from error
                else:
                    raise StorageError(f"Could not publish the PDF blob: {error}") from error

            return StoredBlob(sha256, relative, size, created)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def verify(
        self, relative_path: str, expected_sha256: str, expected_size: int
    ) -> IntegrityResult:
        """Check a blob without changing either bytes or recorded identity."""
        path = self.resolve(relative_path, expected_sha256)
        if not path.is_file():
            return IntegrityResult(
                False,
                expected_sha256,
                None,
                expected_size,
                None,
                "The stored PDF blob is missing.",
            )
        actual_size = path.stat().st_size
        actual_sha256 = sha256_file(path)
        ok = actual_sha256 == expected_sha256 and actual_size == expected_size
        if ok:
            message = "Stored bytes match the recorded SHA-256 and file size."
        elif actual_sha256 != expected_sha256:
            message = "Integrity mismatch: stored bytes have a different SHA-256."
        else:
            message = "Integrity mismatch: stored file size differs from the record."
        return IntegrityResult(
            ok,
            expected_sha256,
            actual_sha256,
            expected_size,
            actual_size,
            message,
        )
