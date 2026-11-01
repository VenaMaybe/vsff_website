"""Validation and persistence for immutable, exact-version anchor instances."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .database import connect, transaction
from .documents import get_version, now_utc


ANCHOR_SCHEMA_VERSION = 1
TEXT_SELECTOR_VERSION = "pdfjs-dom-text-v1"
TEXT_CONTEXT_LENGTH = 96
MAX_ANCHOR_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_SELECTION_TEXT_LENGTH = 100_000
MAX_PAGE_TEXT_LENGTH = 1_000_000
MAX_SEGMENTS = 100
MAX_RECTANGLES_PER_SEGMENT = 1_000
MAX_PDF_PAGES = 100_000
MAX_COORDINATE_MAGNITUDE = 10_000_000
GEOMETRY_TOLERANCE = 0.01


class AnchorError(RuntimeError):
    """Base class for controlled anchor errors."""


class AnchorValidationError(AnchorError):
    """The submitted anchor bundle failed strict validation."""


class AnchorVersionNotFoundError(AnchorError):
    """The exact document version for an anchor does not exist."""


class AnchorNotFoundError(AnchorError):
    """The requested anchor does not exist."""


class AnchorInUseError(AnchorError):
    """The anchor is an immutable target of a review thread."""


@dataclass(frozen=True)
class ValidatedSegment:
    segment_index: int
    page_number: int
    rectangles: list[list[float]]
    pdf_view_box: list[float]
    capture_viewport_width: float
    capture_viewport_height: float
    capture_rotation: int
    exact_text: str
    prefix_text: str
    suffix_text: str
    text_start: int | None
    text_end: int | None
    page_text_sha256: str | None


@dataclass(frozen=True)
class ValidatedAnchor:
    selection_text: str
    page_count: int
    segments: list[ValidatedSegment]


def _require_exact_keys(
    value: dict[str, Any], expected: set[str], label: str
) -> None:
    actual = set(value)
    missing = expected - actual
    unexpected = actual - expected
    if missing:
        raise AnchorValidationError(
            f"{label} is missing required field(s): {', '.join(sorted(missing))}."
        )
    if unexpected:
        raise AnchorValidationError(
            f"{label} contains unsupported field(s): {', '.join(sorted(unexpected))}."
        )


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnchorValidationError(f"{label} must be an integer.")
    if value < minimum or value > maximum:
        raise AnchorValidationError(
            f"{label} must be between {minimum} and {maximum}."
        )
    return value


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnchorValidationError(f"{label} must be a finite number.")
    result = float(value)
    if not math.isfinite(result) or abs(result) > MAX_COORDINATE_MAGNITUDE:
        raise AnchorValidationError(f"{label} must be a finite, reasonable number.")
    return result


def _text(value: Any, label: str, maximum: int, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise AnchorValidationError(f"{label} must be text.")
    if len(value) > maximum:
        raise AnchorValidationError(f"{label} exceeds {maximum} characters.")
    if not allow_empty and not value.strip():
        raise AnchorValidationError(f"{label} must not be empty.")
    return value


def _validate_view_box(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) != 4:
        raise AnchorValidationError("pdf_view_box must contain four coordinates.")
    box = [_finite_number(item, "pdf_view_box coordinate") for item in value]
    if box[0] >= box[2] or box[1] >= box[3]:
        raise AnchorValidationError("pdf_view_box must have positive width and height.")
    return box


def _validate_rectangles(value: Any, view_box: list[float]) -> list[list[float]]:
    if not isinstance(value, list) or not value:
        raise AnchorValidationError("A text segment must contain at least one rectangle.")
    if len(value) > MAX_RECTANGLES_PER_SEGMENT:
        raise AnchorValidationError("A text segment contains too many rectangles.")
    rectangles: list[list[float]] = []
    for index, item in enumerate(value):
        if not isinstance(item, list) or len(item) != 4:
            raise AnchorValidationError(f"Rectangle {index} must contain four coordinates.")
        rectangle = [
            _finite_number(number, f"Rectangle {index} coordinate") for number in item
        ]
        x1, y1, x2, y2 = rectangle
        if x1 >= x2 or y1 >= y2:
            raise AnchorValidationError(
                f"Rectangle {index} must be canonical with positive width and height."
            )
        if (
            x1 < view_box[0] - GEOMETRY_TOLERANCE
            or y1 < view_box[1] - GEOMETRY_TOLERANCE
            or x2 > view_box[2] + GEOMETRY_TOLERANCE
            or y2 > view_box[3] + GEOMETRY_TOLERANCE
        ):
            raise AnchorValidationError(
                f"Rectangle {index} lies outside the declared PDF page view box."
            )
        rectangles.append(rectangle)
    return rectangles


def _validate_capture_viewport(value: Any) -> tuple[float, float, int]:
    if not isinstance(value, dict):
        raise AnchorValidationError("capture_viewport must be an object.")
    _require_exact_keys(value, {"width", "height", "rotation"}, "capture_viewport")
    width = _finite_number(value["width"], "capture_viewport.width")
    height = _finite_number(value["height"], "capture_viewport.height")
    if width <= 0 or height <= 0:
        raise AnchorValidationError("Capture viewport dimensions must be positive.")
    rotation = _integer(value["rotation"], "capture_viewport.rotation", 0, 270)
    if rotation not in (0, 90, 180, 270):
        raise AnchorValidationError("Capture rotation must be 0, 90, 180, or 270.")
    return width, height, rotation


def _validate_selector(segment: dict[str, Any]) -> tuple[str, str, str, int | None, int | None, str | None]:
    exact_text = _text(
        segment["exact_text"], "segment exact_text", MAX_SELECTION_TEXT_LENGTH, False
    )
    prefix = _text(segment["prefix"], "segment prefix", TEXT_CONTEXT_LENGTH)
    suffix = _text(segment["suffix"], "segment suffix", TEXT_CONTEXT_LENGTH)
    page_text = segment["page_text"]
    start = segment["text_start"]
    end = segment["text_end"]

    if page_text is None:
        if start is not None or end is not None:
            raise AnchorValidationError(
                "Selector offsets require the temporary page_text provenance value."
            )
        return exact_text, prefix, suffix, None, None, None

    page_text = _text(page_text, "segment page_text", MAX_PAGE_TEXT_LENGTH)
    start = _integer(start, "segment text_start", 0, len(page_text))
    end = _integer(end, "segment text_end", start, len(page_text))
    if page_text[start:end] != exact_text:
        raise AnchorValidationError(
            "The selector offsets do not identify the submitted segment exact_text."
        )
    expected_prefix = page_text[max(0, start - TEXT_CONTEXT_LENGTH) : start]
    expected_suffix = page_text[end : end + TEXT_CONTEXT_LENGTH]
    if prefix != expected_prefix or suffix != expected_suffix:
        raise AnchorValidationError(
            "The submitted selector context does not match the page text and offsets."
        )
    fingerprint = hashlib.sha256(page_text.encode("utf-8")).hexdigest()
    return exact_text, prefix, suffix, start, end, fingerprint


def validate_anchor_payload(payload: Any) -> ValidatedAnchor:
    """Validate an untrusted JSON anchor bundle before starting a transaction."""
    if not isinstance(payload, dict):
        raise AnchorValidationError("The anchor payload must be a JSON object.")
    _require_exact_keys(
        payload,
        {
            "anchor_kind",
            "selection_text",
            "selector_version",
            "anchor_schema_version",
            "page_count",
            "segments",
        },
        "anchor payload",
    )
    if payload["anchor_kind"] != "text":
        raise AnchorValidationError("Slice 2 can create only text anchors.")
    if payload["selector_version"] != TEXT_SELECTOR_VERSION:
        raise AnchorValidationError(
            f"selector_version must be {TEXT_SELECTOR_VERSION}."
        )
    if payload["anchor_schema_version"] != ANCHOR_SCHEMA_VERSION:
        raise AnchorValidationError(
            f"anchor_schema_version must be {ANCHOR_SCHEMA_VERSION}."
        )
    selection_text = _text(
        payload["selection_text"],
        "selection_text",
        MAX_SELECTION_TEXT_LENGTH,
        False,
    )
    page_count = _integer(payload["page_count"], "page_count", 1, MAX_PDF_PAGES)
    raw_segments = payload["segments"]
    if not isinstance(raw_segments, list) or not raw_segments:
        raise AnchorValidationError("A text anchor must contain at least one segment.")
    if len(raw_segments) > MAX_SEGMENTS:
        raise AnchorValidationError("The anchor contains too many page segments.")

    segments: list[ValidatedSegment] = []
    expected_keys = {
        "segment_index",
        "page_number",
        "rectangles",
        "pdf_view_box",
        "capture_viewport",
        "exact_text",
        "prefix",
        "suffix",
        "text_start",
        "text_end",
        "page_text",
    }
    for position, raw_segment in enumerate(raw_segments):
        if not isinstance(raw_segment, dict):
            raise AnchorValidationError(f"Segment {position} must be an object.")
        _require_exact_keys(raw_segment, expected_keys, f"Segment {position}")
        segment_index = _integer(
            raw_segment["segment_index"], f"Segment {position} index", 0, MAX_SEGMENTS - 1
        )
        if segment_index != position:
            raise AnchorValidationError(
                "Segment indexes must be unique, contiguous, and match array order."
            )
        page_number = _integer(
            raw_segment["page_number"], f"Segment {position} page_number", 1, page_count
        )
        if segments and page_number != segments[-1].page_number + 1:
            raise AnchorValidationError(
                "Multi-page text segments must use consecutive pages in ascending order."
            )
        view_box = _validate_view_box(raw_segment["pdf_view_box"])
        rectangles = _validate_rectangles(raw_segment["rectangles"], view_box)
        viewport_width, viewport_height, rotation = _validate_capture_viewport(
            raw_segment["capture_viewport"]
        )
        exact, prefix, suffix, start, end, fingerprint = _validate_selector(raw_segment)
        segments.append(
            ValidatedSegment(
                segment_index,
                page_number,
                rectangles,
                view_box,
                viewport_width,
                viewport_height,
                rotation,
                exact,
                prefix,
                suffix,
                start,
                end,
                fingerprint,
            )
        )
    return ValidatedAnchor(selection_text, page_count, segments)


def _insert_segment(
    connection: sqlite3.Connection, anchor_id: str, segment: ValidatedSegment
) -> None:
    connection.execute(
        """
        INSERT INTO anchor_segments(
            segment_id, anchor_id, segment_index, page_number,
            rectangles_json, pdf_view_box_json,
            capture_viewport_width, capture_viewport_height, capture_rotation,
            exact_text, prefix_text, suffix_text,
            text_start, text_end, page_text_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            anchor_id,
            segment.segment_index,
            segment.page_number,
            json.dumps(segment.rectangles, separators=(",", ":")),
            json.dumps(segment.pdf_view_box, separators=(",", ":")),
            segment.capture_viewport_width,
            segment.capture_viewport_height,
            segment.capture_rotation,
            segment.exact_text,
            segment.prefix_text,
            segment.suffix_text,
            segment.text_start,
            segment.text_end,
            segment.page_text_sha256,
        ),
    )


def create_anchor(
    database_path: Path | str, version_id: str, payload: Any
) -> dict[str, Any]:
    """Transactionally persist one immutable anchor and all of its segments."""
    validated = validate_anchor_payload(payload)
    with transaction(database_path) as connection:
        anchor_id = insert_validated_anchor(connection, version_id, validated)
    return get_anchor(database_path, anchor_id)


def insert_validated_anchor(
    connection: sqlite3.Connection,
    version_id: str,
    validated: ValidatedAnchor,
    anchor_id: str | None = None,
) -> str:
    """Insert a validated anchor through an existing transaction.

    Discussion creation uses this seam so the immutable anchor, thread, target,
    and root comment share one all-or-nothing database commit.
    """
    version_exists = connection.execute(
        "SELECT 1 FROM document_versions WHERE version_id = ?", (version_id,)
    ).fetchone()
    if version_exists is None:
        raise AnchorVersionNotFoundError("The document version does not exist.")
    anchor_id = anchor_id or str(uuid.uuid4())
    connection.execute(
        """
        INSERT INTO anchor_instances(
            anchor_id, document_version_id, anchor_kind, selection_text,
            selector_version, anchor_schema_version, created_at
        ) VALUES (?, ?, 'text', ?, ?, ?, ?)
        """,
        (
            anchor_id,
            version_id,
            validated.selection_text,
            TEXT_SELECTOR_VERSION,
            ANCHOR_SCHEMA_VERSION,
            now_utc(),
        ),
    )
    for segment in validated.segments:
        _insert_segment(connection, anchor_id, segment)
    return anchor_id


def _serialize_anchor_row(
    anchor: sqlite3.Row, segments: list[sqlite3.Row]
) -> dict[str, Any]:
    serialized_segments = []
    for segment in segments:
        selector_verified = (
            segment["text_start"] is not None
            and segment["text_end"] is not None
            and segment["page_text_sha256"] is not None
        )
        serialized_segments.append(
            {
                "segment_id": segment["segment_id"],
                "segment_index": segment["segment_index"],
                "page_number": segment["page_number"],
                "rectangles": json.loads(segment["rectangles_json"]),
                "pdf_view_box": json.loads(segment["pdf_view_box_json"]),
                "capture_viewport": {
                    "width": segment["capture_viewport_width"],
                    "height": segment["capture_viewport_height"],
                    "rotation": segment["capture_rotation"],
                },
                "exact_text": segment["exact_text"],
                "prefix": segment["prefix_text"],
                "suffix": segment["suffix_text"],
                "text_start": segment["text_start"],
                "text_end": segment["text_end"],
                "page_text_sha256": segment["page_text_sha256"],
                "validation": {
                    "geometry": "validated",
                    "selector": "verified" if selector_verified else "unverified",
                },
            }
        )
    return {
        "anchor_id": anchor["anchor_id"],
        "document_version_id": anchor["document_version_id"],
        "anchor_kind": anchor["anchor_kind"],
        "selection_text": anchor["selection_text"],
        "selector_version": anchor["selector_version"],
        "anchor_schema_version": anchor["anchor_schema_version"],
        "created_at": anchor["created_at"],
        "segments": serialized_segments,
    }


def get_anchor(database_path: Path | str, anchor_id: str) -> dict[str, Any]:
    connection = connect(database_path)
    try:
        anchor = connection.execute(
            "SELECT * FROM anchor_instances WHERE anchor_id = ?", (anchor_id,)
        ).fetchone()
        if anchor is None:
            raise AnchorNotFoundError("The anchor does not exist.")
        segments = connection.execute(
            """
            SELECT * FROM anchor_segments
            WHERE anchor_id = ?
            ORDER BY segment_index ASC, segment_id ASC
            """,
            (anchor_id,),
        ).fetchall()
        return _serialize_anchor_row(anchor, segments)
    finally:
        connection.close()


def list_anchors(database_path: Path | str, version_id: str, *, standalone_only: bool = False) -> list[dict[str, Any]]:
    if get_version(database_path, version_id) is None:
        raise AnchorVersionNotFoundError("The document version does not exist.")
    connection = connect(database_path)
    try:
        standalone_clause = "AND NOT EXISTS (SELECT 1 FROM thread_targets tt WHERE tt.anchor_id = anchor_instances.anchor_id)" if standalone_only else ""
        anchor_rows = connection.execute(
            f"""
            SELECT * FROM anchor_instances
            WHERE document_version_id = ? {standalone_clause}
            ORDER BY created_at ASC, anchor_id ASC
            """,
            (version_id,),
        ).fetchall()
        if not anchor_rows:
            return []
        anchor_ids = [row["anchor_id"] for row in anchor_rows]
        placeholders = ",".join("?" for _ in anchor_ids)
        segment_rows = connection.execute(
            f"""
            SELECT * FROM anchor_segments
            WHERE anchor_id IN ({placeholders})
            ORDER BY anchor_id ASC, segment_index ASC, segment_id ASC
            """,
            anchor_ids,
        ).fetchall()
        grouped: dict[str, list[sqlite3.Row]] = {anchor_id: [] for anchor_id in anchor_ids}
        for segment in segment_rows:
            grouped[segment["anchor_id"]].append(segment)
        return [
            _serialize_anchor_row(anchor, grouped[anchor["anchor_id"]])
            for anchor in anchor_rows
        ]
    finally:
        connection.close()


def delete_anchor(database_path: Path | str, anchor_id: str) -> None:
    try:
        with transaction(database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM anchor_instances WHERE anchor_id = ?", (anchor_id,)
            )
            if cursor.rowcount != 1:
                raise AnchorNotFoundError("The anchor does not exist.")
    except sqlite3.IntegrityError as error:
        if "FOREIGN KEY constraint failed" in str(error):
            raise AnchorInUseError(
                "An anchor used by a review thread cannot be deleted."
            ) from error
        raise
