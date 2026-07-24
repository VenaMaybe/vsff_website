
pieces = [
	{
		"id": 1,
		"title": "Flowers for the Uninitiated",
	},
	{
		"id": 2,
		"title": "In the Shadows of Giants",
	},
]


@app.get("/")
def index():
	return {
		"message": "Writing competition API",
		"available_routes": [
			"GET /api/health",
			"GET /api/pieces",
			"GET /api/pieces/<id>",
			"POST /api/pieces",
		],
	}


@app.get("/api/health")
def health():
	return {
		"status": "ok",
	}


@app.get("/api/pieces")
def get_pieces():
	return {
		"count": len(pieces),
		"pieces": pieces,
	}


@app.get("/api/pieces/<int:piece_id>")
def get_piece(piece_id):
	piece = next(
		(piece for piece in pieces if piece["id"] == piece_id),
		None,
	)

	if piece is None:
		return {
			"error": "Piece not found",
		}, 404

	return piece


@app.post("/api/pieces")
def create_piece():
	data = request.get_json(silent=True)

	if not data:
		return {
			"error": "Request body must contain JSON",
		}, 400

	title = data.get("title")

	if not isinstance(title, str) or not title.strip():
		return {
			"error": "title is required",
		}, 400

	piece = {
		"id": max((piece["id"] for piece in pieces), default=0) + 1,
		"title": title.strip(),
	}

	pieces.append(piece)

	return piece, 201