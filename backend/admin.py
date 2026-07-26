import os
from functools import wraps

from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash

from extensions import db, socketio
from dbmodels import Comment


admin_blueprint = Blueprint(
	"admin",
	__name__,
	url_prefix="/api/admin",
)


def admin_is_authenticated():
	return session.get("comments_admin") is True


def admin_required(route_function):
	@wraps(route_function)
	def protected_route(*args, **kwargs):
		if not admin_is_authenticated():
			return jsonify({
				"error": "Admin authentication required.",
			}), 401

		return route_function(
			*args,
			**kwargs,
		)

	return protected_route


@admin_blueprint.post("/login")
def admin_login():
	data = request.get_json(silent=True)

	if not isinstance(data, dict):
		return jsonify({
			"error": "Request must contain JSON.",
		}), 400

	password = data.get("password")

	if not isinstance(password, str):
		return jsonify({
			"error": "Password must be text.",
		}), 400

	password_hash = os.getenv("ADMIN_PASSWORD_HASH")

	if not password_hash:
		return jsonify({
			"error": "Admin password is not configured.",
		}), 500

	if not check_password_hash(
		password_hash,
		password,
	):
		return jsonify({
			"error": "Incorrect password.",
		}), 401

	session.clear()
	session["comments_admin"] = True
	session.permanent = True

	return jsonify({
		"authenticated": True,
	})


@admin_blueprint.get("/session")
def get_admin_session():
	return jsonify({
		"authenticated": admin_is_authenticated(),
	})


@admin_blueprint.post("/logout")
def admin_logout():
	session.clear()

	return jsonify({
		"authenticated": False,
	})


@admin_blueprint.get("/comments")
@admin_required
def get_admin_comments():
	comments = db.session.execute(
		db.select(Comment)
		.order_by(Comment.id.desc())
	).scalars().all()

	return jsonify([
		comment.to_admin_dict()
		for comment in comments
	])


@admin_blueprint.patch("/comments/<int:comment_id>")
@admin_required
def update_admin_comment(comment_id):
	data = request.get_json(silent=True)

	if not isinstance(data, dict):
		return jsonify({
			"error": "Request must contain JSON.",
		}), 400

	hidden = data.get("hidden")

	if not isinstance(hidden, bool):
		return jsonify({
			"error": "Hidden must be true or false.",
		}), 400

	comment = db.session.get(
		Comment,
		comment_id,
	)

	if comment is None:
		return jsonify({
			"error": "Comment not found.",
		}), 404

	comment.hidden = hidden

	try:
		db.session.commit()
	except SQLAlchemyError:
		db.session.rollback()

		return jsonify({
			"error": "Could not update the comment.",
		}), 500

	socketio.emit(
		"comment_visibility_changed",
		{
			"id": comment.id,
			"hidden": comment.hidden,
		},
		namespace="/comments",
	)

	return jsonify(
		comment.to_admin_dict(),
	)