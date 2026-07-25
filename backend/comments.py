from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

# A blueprint is a mini section of the flask app
# comments = flasks name for this group of routes
#

# for the database
def create_comments_blueprint(db, socketio):
	# Naming the blueprint
	comments_blueprint = Blueprint(
		"comments",
		__name__,
	)

	# Comments table structure
	class Comment(db.Model):
		__tablename__ = "comments"

		id = db.Column(
			db.Integer,
			primary_key=True,
		)

		name = db.Column(
			db.String(30),
			nullable=False,
		)

		body = db.Column(
			db.String(250),
			nullable=False,
		)

		created_at = db.Column(
			db.DateTime(),
			nullable=False,
			default=lambda: datetime.now(
				timezone.utc,
			).replace(tzinfo=None),
		)

		def to_dict(self):
			created_at = self.created_at

			if created_at.tzinfo is None:
				created_at = created_at.replace(
					tzinfo=timezone.utc,
				)

			return {
				"id": self.id,
				"name": self.name,
				"body": self.body,
				"createdAt": created_at.isoformat(),
			}

	# Gets the comments table
	@comments_blueprint.get("/api/comments")
	def get_comments():
		comments = db.session.execute(
			db.select(Comment)
			.order_by(Comment.id.desc())
			.limit(100)
		).scalars().all()

		comments.reverse()

		return jsonify([
			comment.to_dict()
			for comment in comments
		])

	# inserts something into the comments table
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

	return comments_blueprint