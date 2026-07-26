from datetime import datetime, timezone

from sqlalchemy import false

from extensions import db


class Comment(db.Model):
	__tablename__ = "comments"

	def __init__(
		self,
		*,
		name: str,
		body: str,
		ip_address: str | None = None,
	) -> None:
		self.name = name
		self.body = body
		self.ip_address = ip_address

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

	ip_address = db.Column(
		db.String(45),
		nullable=True,
	)

	hidden = db.Column(
		db.Boolean,
		nullable=False,
		default=False,
		server_default=false(),
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

	def to_admin_dict(self):
		return {
			**self.to_dict(),
			"ipAddress": self.ip_address,
			"hidden": self.hidden,
		}