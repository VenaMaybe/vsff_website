"""Public beta policies; these pages never load private account or review data."""

from flask import Blueprint, render_template, request


bp = Blueprint("legal", __name__)
PUBLIC_ENDPOINTS = {"legal.privacy", "legal.terms"}


def policy(template):
    # A non-authoritative display cookie only; retain public, database-free reads.
    theme='dark' if request.cookies.get('pdf_review_ui_theme')=='dark' else 'light'
    return render_template(template,public_ui_theme=theme)


@bp.get("/privacy", provide_automatic_options=False)
def privacy():
    return policy("privacy.html")


@bp.get("/tos", provide_automatic_options=False)
def terms():
    return policy("terms.html")
