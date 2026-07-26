from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from extensions import db, socketio
from dbmodels import Comment


comments_blueprint = Blueprint(
	"comments",
	__name__,
)


@comments_blueprint.get("/api/comments")
def get_comments():
	comments = list(
		db.session.execute(
			db.select(Comment)
			.where(Comment.hidden.is_(False))
			.order_by(Comment.id.desc())
			.limit(100)
		).scalars().all()
	)

	comments.reverse()

	return jsonify([
		comment.to_dict()
		for comment in comments
	])


@comments_blueprint.post("/api/comments")
def create_comment():
	data = request.get_json(silent=True)

	if not isinstance(data, dict):
		return jsonify({
			"error": "Request must contain JSON.",
		}), 400

	name = data.get("name")
	body = data.get("body")

	if not isinstance(name, str):
		return jsonify({
			"error": "Name must be text.",
		}), 400

	if not isinstance(body, str):
		return jsonify({
			"error": "Comment must be text.",
		}), 400

	name = name.strip()
	body = body.strip()

	if not name:
		return jsonify({
			"error": "Please enter a name.",
		}), 400

	if not body:
		return jsonify({
			"error": "Please enter a comment.",
		}), 400

	if len(name) > 30:
		return jsonify({
			"error": "Name cannot exceed 30 characters.",
		}), 400

	if len(body) > 250:
		return jsonify({
			"error": "Comment cannot exceed 250 characters.",
		}), 400

	comment = Comment(
		name=name,
		body=body,
		ip_address=request.remote_addr,
	)

	try:
		db.session.add(comment)
		db.session.commit()
	except SQLAlchemyError:
		db.session.rollback()

		return jsonify({
			"error": "Could not save the comment.",
		}), 500

	comment_data = comment.to_dict()

	socketio.emit(
		"comment_created",
		comment_data,
		namespace="/comments",
	)

	return jsonify(comment_data), 201


@socketio.on(
	"connect",
	namespace="/comments",
)
def connect_to_comments():
	print("Someone connected to live comments.")