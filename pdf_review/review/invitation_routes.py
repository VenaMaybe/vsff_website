"""Invitation and membership UI. Anonymous landing pages disclose no recipient data."""

from flask import Blueprint, abort, current_app, g, jsonify, redirect, render_template, request, session, url_for

from . import invitations as service
from .access import AccessDenied, AccessError
from .auth import current_user, IdentityDenied


bp = Blueprint('invites', __name__)


def database():
    return current_app.config['DATABASE']


def actor():
    return g.auth_user['user_id']


@bp.errorhandler(AccessDenied)
def denied(error):
    return render_template('error.html', title='Request denied', message=str(error)), 403


@bp.errorhandler(AccessError)
@bp.errorhandler(IdentityDenied)
def invalid(error):
    if request.accept_mimetypes.best == 'application/json':
        return jsonify(error={'message': str(error)}), 422
    return render_template('error.html', title='Invitation unavailable', message=str(error)), 422


def fields(allowed):
    if set(request.form) - set(allowed) - {'csrf_token'}:
        abort(400)


@bp.get('/invitations')
def manage():
    return render_template('invitations.html', invitations=service.list_invitations(database(), actor()))


@bp.get('/members')
def members():
    return render_template('members.html', members=service.directory(database(), actor()))


@bp.post('/invitations')
def beta_create():
    fields({'email'})
    row = service.create_invitation(database(), actor(), request.form.get('email'))
    return redirect(url_for('invites.detail', invitation_id=row['invitation_id']), code=303)


@bp.post('/documents/<document_id>/invitations')
def document_create(document_id):
    fields({'email', 'role'})
    row = service.create_invitation(database(), actor(), request.form.get('email'), document_id, request.form.get('role'))
    if request.accept_mimetypes.best == 'application/json':
        active = row['status'] == 'pending' and row['expires_at'] > service.now_utc()
        link = url_for('invites.landing', invitation_id=row['invitation_id'], _external=True,
                       _scheme=current_app.config['PREFERRED_URL_SCHEME']) + '#token=' + service.token_for(current_app.secret_key, row) if active else None
        return jsonify(status=row['status'], email=row['normalized_email'], invitation_link=link,
                       manage_url=url_for('invites.detail', invitation_id=row['invitation_id']))
    return redirect(url_for('invites.detail', invitation_id=row['invitation_id']), code=303)


@bp.get('/invitations/<invitation_id>/manage')
def detail(invitation_id):
    row = service.invitation_detail(database(), actor(), invitation_id)
    active = row['status'] == 'pending' and row['expires_at'] > service.now_utc()
    link = url_for('invites.landing', invitation_id=invitation_id, _external=True,
                   _scheme=current_app.config['PREFERRED_URL_SCHEME']) + '#token=' + service.token_for(current_app.secret_key, row) if active else None
    return render_template('invitation_detail.html', invitation=row, invitation_link=link)


@bp.post('/invitations/<invitation_id>/manage')
def mutate(invitation_id):
    fields({'action'})
    action = request.form.get('action')
    if action == 'revoke':
        service.revoke_invitation(database(), actor(), invitation_id)
    elif action == 'renew':
        row = service.renew_invitation(database(), actor(), invitation_id)
        invitation_id = row['invitation_id']
    else:
        abort(400)
    return redirect(url_for('invites.detail', invitation_id=invitation_id), code=303)


@bp.get('/invite/<invitation_id>', provide_automatic_options=False)
def landing(invitation_id):
    # A link preview/crawler must neither consume an invitation nor see its email/document.
    return render_template('invitation_landing.html', invitation_id=invitation_id)


@bp.post('/invite/<invitation_id>/open')
def open(invitation_id):
    fields({'token'})
    marker = service.open_link(database(), invitation_id, request.form.get('token'), current_app.secret_key)
    session['pending_invitation'] = marker
    user = current_user()
    if user:
        try:
            document_id = service.accept_existing(database(), marker, user['user_id'])
        except service.WrongInvitationAccount:
            return render_template('invitation_account.html'), 403
        session.pop('pending_invitation', None)
        destination = url_for('core.document_detail', document_id=document_id) if document_id else url_for('core.dashboard')
        return redirect(destination, code=303)
    return redirect(url_for('auth.google_login'), code=303)


@bp.post('/admin/trusted-users')
def trusted():
    fields({'user_id', 'action'})
    action = request.form.get('action')
    if action not in {'grant', 'revoke'}:
        abort(400)
    service.set_trusted(database(), actor(), request.form.get('user_id'), action == 'grant')
    return redirect(url_for('accounts.admin'), code=303)


@bp.post('/admin/attribute-legacy-members')
def legacy():
    fields({'confirm'})
    if request.form.get('confirm') != 'yes':
        abort(400)
    service.backfill_legacy(database(), actor())
    return redirect(url_for('invites.members'), code=303)


@bp.get('/admin/history')
def history():
    before = request.args.get('before', type=int)
    if 'before' in request.args and (before is None or before < 1):
        abort(400)
    events = service.audit_history(database(), actor(), before)
    return render_template('access_history.html', events=events)
