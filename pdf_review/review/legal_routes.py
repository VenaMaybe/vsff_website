"""Public beta policies; these pages never load private account or review data."""

from flask import Blueprint, render_template


bp = Blueprint("legal", __name__)
PUBLIC_ENDPOINTS = {"legal.privacy", "legal.terms"}


@bp.get("/privacy", provide_automatic_options=False)
def privacy():
    return render_template("privacy.html")


@bp.get("/tos", provide_automatic_options=False)
def terms():
    return render_template("terms.html")
