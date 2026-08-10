import hashlib
import html
import json
import os
import re
import struct
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlencode, urljoin

from flask import (
	Blueprint,
	Response,
	current_app,
	jsonify,
	request,
	send_from_directory,
	url_for,
)


color_previews_blueprint = Blueprint(
	"color_previews",
	__name__,
)

PREVIEW_WIDTH = 1200
PREVIEW_HEIGHT = 630
MAX_PREVIEW_BYTES = 2 * 1024 * 1024
MAX_PRESET_LENGTH = 16_000
MAX_UPLOADS_PER_HOUR = 60

_PREVIEW_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_PRESET_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_upload_times = defaultdict(deque)
_upload_lock = threading.Lock()


def _preview_directory():
	configured_directory = os.getenv(
		"COLOR_PREVIEW_DIRECTORY",
	)

	if configured_directory:
		directory = Path(configured_directory)
	else:
		directory = (
			Path(current_app.instance_path)
			/ "color_previews"
		)

	directory.mkdir(
		parents=True,
		exist_ok=True,
	)

	return directory


def _valid_png(data):
	if (
		len(data) < 24
		or data[:8] != b"\x89PNG\r\n\x1a\n"
		or data[12:16] != b"IHDR"
		or data[-12:] != b"\x00\x00\x00\x00IEND\xaeB\x60\x82"
	):
		return False

	width, height = struct.unpack(
		">II",
		data[16:24],
	)

	return (
		width == PREVIEW_WIDTH
		and height == PREVIEW_HEIGHT
	)


def _upload_allowed():
	now = time.monotonic()
	cutoff = now - 3600
	client_key = request.remote_addr or "unknown"

	with _upload_lock:
		timestamps = _upload_times[client_key]

		while timestamps and timestamps[0] < cutoff:
			timestamps.popleft()

		if len(timestamps) >= MAX_UPLOADS_PER_HOUR:
			return False

		timestamps.append(now)

	return True


@color_previews_blueprint.post("/api/color-previews")
def create_color_preview():
	if not _upload_allowed():
		return jsonify({
			"error": "Too many color previews were created recently.",
		}), 429

	preview = request.files.get("preview")

	if preview is None:
		return jsonify({
			"error": "A preview image is required.",
		}), 400

	data = preview.stream.read(
		MAX_PREVIEW_BYTES + 1,
	)

	if len(data) > MAX_PREVIEW_BYTES:
		return jsonify({
			"error": "The preview image is too large.",
		}), 413

	if not _valid_png(data):
		return jsonify({
			"error": "The preview must be a 1200 by 630 PNG image.",
		}), 400

	preview_id = hashlib.sha256(data).hexdigest()[:32]
	preview_path = (
		_preview_directory()
		/ f"{preview_id}.png"
	)

	if not preview_path.exists():
		temporary_path = preview_path.with_suffix(
			".png.tmp",
		)
		temporary_path.write_bytes(data)
		os.replace(
			temporary_path,
			preview_path,
		)

	return jsonify({
		"previewId": preview_id,
		"sharePath": f"/api/color-share/{preview_id}",
	})


@color_previews_blueprint.get(
	"/api/color-previews/<preview_id>.png",
)
def get_color_preview(preview_id):
	if not _PREVIEW_ID_PATTERN.fullmatch(preview_id):
		return jsonify({
			"error": "Invalid color preview.",
		}), 404

	response = send_from_directory(
		_preview_directory(),
		f"{preview_id}.png",
		mimetype="image/png",
		conditional=True,
	)
	response.headers["Cache-Control"] = (
		"public, max-age=31536000, immutable"
	)

	return response


@color_previews_blueprint.get(
	"/api/color-share/<preview_id>",
)
def get_color_share(preview_id):
	preset = request.args.get(
		"preset",
		"",
	)

	if (
		not _PREVIEW_ID_PATTERN.fullmatch(preview_id)
		or not preset
		or len(preset) > MAX_PRESET_LENGTH
		or not _PRESET_PATTERN.fullmatch(preset)
	):
		return jsonify({
			"error": "Invalid color scene share link.",
		}), 400

	preview_path = (
		_preview_directory()
		/ f"{preview_id}.png"
	)

	if not preview_path.is_file():
		return jsonify({
			"error": "This color preview is no longer available.",
		}), 404

	preset_name = request.args.get(
		"name",
		"",
	).strip()[:80]
	title = (
		f"{preset_name} — Vena's Color Explorer"
		if preset_name
		else "Vena's Color Explorer"
	)
	description = (
		"Explore this interactive 3D color-space scene and fly through "
		"its palette deformation."
	)
	color_url = urljoin(
		request.host_url,
		"colors",
	)
	color_url = (
		f"{color_url}?{urlencode({'preset': preset})}"
	)
	image_url = url_for(
		"color_previews.get_color_preview",
		preview_id=preview_id,
		_external=True,
	)

	escaped_title = html.escape(
		title,
		quote=True,
	)
	escaped_description = html.escape(
		description,
		quote=True,
	)
	escaped_color_url = html.escape(
		color_url,
		quote=True,
	)
	escaped_image_url = html.escape(
		image_url,
		quote=True,
	)
	redirect_url = json.dumps(color_url)

	document = f"""<!doctype html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<meta name="description" content="{escaped_description}">
	<link rel="canonical" href="{escaped_color_url}">
	<meta property="og:type" content="website">
	<meta property="og:site_name" content="Vena's Color Explorer">
	<meta property="og:url" content="{escaped_color_url}">
	<meta property="og:title" content="{escaped_title}">
	<meta property="og:description" content="{escaped_description}">
	<meta property="og:image" content="{escaped_image_url}">
	<meta property="og:image:secure_url" content="{escaped_image_url}">
	<meta property="og:image:type" content="image/png">
	<meta property="og:image:width" content="{PREVIEW_WIDTH}">
	<meta property="og:image:height" content="{PREVIEW_HEIGHT}">
	<meta property="og:image:alt" content="Preview of the shared color-space scene">
	<meta name="twitter:card" content="summary_large_image">
	<meta name="twitter:title" content="{escaped_title}">
	<meta name="twitter:description" content="{escaped_description}">
	<meta name="twitter:image" content="{escaped_image_url}">
	<title>{escaped_title}</title>
	<script>window.location.replace({redirect_url})</script>
</head>
<body>
	<p>Opening <a href="{escaped_color_url}">{escaped_title}</a>…</p>
</body>
</html>"""

	response = Response(
		document,
		mimetype="text/html",
	)
	response.headers["Cache-Control"] = (
		"public, max-age=300"
	)

	return response
