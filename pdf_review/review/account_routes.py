"""Thin server-rendered account, owner sharing and beta administration surfaces."""

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from . import access
from .auth import IdentityDenied
from .documents import get_document
from .users import UserValidationError

bp = Blueprint('accounts', __name__)


def database():
    return current_app.config['DATABASE']


def actor():
    return g.auth_user['user_id']


@bp.errorhandler(access.AccessDenied)
def permission_changed(error):
    return render_template('error.html', title='Request denied',
                           message='Permission has changed. Refresh and try again.'), 403


def mutate(operation, destination, **arguments):
    try:
        operation()
    except (access.AccessError, UserValidationError, IdentityDenied) as error:
        # Render errors as an explicit failure, preserving a useful safe explanation.
        return render_template('error.html', title='Change not saved', message=str(error)), 422
    flash('Change saved.', 'success')
    return redirect(url_for(destination, **arguments), code=303)


@bp.get('/account')
def account():
    from .preferences import palette
    documents = access.account_documents(database(), actor())
    return render_template('account.html', owned=[d for d in documents if d['role'] == 'owner'],
                           shared=[d for d in documents if d['role'] != 'owner'], palette=palette(database()))


@bp.post('/account/profile')
def profile():
    if set(request.form) - {'csrf_token', 'display_name'}:
        abort(400)
    return mutate(lambda: access.update_profile(database(), actor(), request.form.get('display_name')), 'accounts.account')


@bp.get('/documents/<document_id>/access')
def access_page(document_id):
    document = get_document(database(), document_id)
    if document is None:
        abort(404)
    return render_template('access.html', document=document, grants=access.document_grants(database(), document_id),
                           shareable=access.shareable_users(database()))


@bp.get('/api/documents/<document_id>/shareable-users')
def shareable(document_id):
    # Owner-scoped directory, never the administrative user listing.
    return jsonify(users=access.shareable_users(database()))


@bp.post('/documents/<document_id>/access')
def access_mutation(document_id):
    if set(request.form) - {'csrf_token', 'user_id', 'role', 'action'}:
        abort(400)
    action = request.form.get('action')
    if action not in {'grant', 'revoke'}:
        abort(400)
    return mutate(lambda: access.set_document_access(database(), document_id, request.form.get('user_id'),
                  None if action == 'revoke' else request.form.get('role', ''), actor=actor()),
                  'accounts.access_page', document_id=document_id)


@bp.get('/admin')
def admin():
    return render_template('admin.html', emails=access.list_allowed_emails(database()),
                           users=access.list_identities(database()), admins=access.list_site_admins(database()))


@bp.post('/admin/beta-access')
def beta_email():
    if set(request.form) - {'csrf_token', 'email', 'action', 'note', 'confirm_established'}:
        abort(400)
    return mutate(lambda: access.set_allowed_email(database(), request.form.get('email'), request.form.get('action'),
                  note=request.form.get('note'), confirmed=request.form.get('confirm_established') == 'yes', actor=actor()), 'accounts.admin')


@bp.post('/admin/site-admins')
def site_admin():
    if set(request.form) - {'csrf_token', 'user_id', 'action'}:
        abort(400)
    action = request.form.get('action')
    if action not in {'grant', 'revoke'}:
        abort(400)
    return mutate(lambda: access.set_site_admin(database(), request.form.get('user_id'), action == 'grant', actor=actor()), 'accounts.admin')
