"""Add comments

Revision ID: c936d3e3dc15
Revises: cfb7f0dce7c4
Create Date: 2026-07-24 17:13:01.343387

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c936d3e3dc15'
down_revision = 'cfb7f0dce7c4'
branch_labels = None
depends_on = None


def upgrade():
	op.create_table(
		"comments",
		sa.Column(
			"id",
			sa.Integer(),
			nullable=False,
		),
		sa.Column(
			"name",
			sa.String(length=30),
			nullable=False,
		),
		sa.Column(
			"body",
			sa.String(length=250),
			nullable=False,
		),
		sa.Column(
			"created_at",
			sa.DateTime(),
			nullable=False,
		),
		sa.PrimaryKeyConstraint("id"),
	)


def downgrade():
	op.drop_table("comments")