"""Thin C2 preference, owner section and semantic feedback endpoints."""

from functools import wraps
from flask import Blueprint,abort,g,jsonify,render_template,request,redirect,url_for
from . import preferences,sections,section_feedback
from .access import AccessDenied
from .database import connect
from .documents import get_document,get_version,list_versions
from .routes import database_path,json_payload,exact_fields,ApiPayloadError,api_error
from .threads import ThreadValidationError,CommentConflictError,CommentPermissionError,CommentNotFoundError
from .realtime import notify_version_changed,notify_user_presentation_changed

bp=Blueprint('review_options',__name__)


def actor():
    return g.auth_user['user_id']


def guarded(fn):
    @wraps(fn)
    def call(*args,**kwargs):
        try:
            return fn(*args,**kwargs)
        except ApiPayloadError as error:
            return api_error(error.code,str(error),error.status)
        except AccessDenied:
            abort(403)
        except (LookupError,CommentNotFoundError):
            abort(404)
        except CommentConflictError as error:
            return jsonify(error={'code':'comment_conflict','message':str(error),'current_revision':error.current_revision}),409
        except sections.SectionConflict as error:
            return api_error('review_conflict',str(error),409)
        except CommentPermissionError as error:
            return api_error('access_denied',str(error),403)
        except (preferences.PreferenceError,sections.SectionError,ThreadValidationError) as error:
            return api_error('invalid_review_setting',str(error),422)
    return call


@bp.get('/documents/<document_id>/review-settings')
@guarded
def settings_page(document_id):
    return render_template('review_settings.html',document=get_document(database_path(),document_id),
        settings=preferences.read_preferences(database_path(),document_id,actor())['defaults'])


@bp.post('/documents/<document_id>/review-settings')
@guarded
def settings_save(document_id):
    if set(request.form)-{'csrf_token',*preferences.DEFAULT_CHOICES}:
        abort(400)
    values={k:request.form[k] for k in preferences.DEFAULT_CHOICES if k in request.form}
    try:
        if 'default_spread' in values:
            values['default_spread']=int(values['default_spread'])
    except ValueError:
        raise preferences.PreferenceError('Invalid spread mode.')
    preferences.save_defaults(database_path(),document_id,actor(),values)
    for v in list_versions(database_path(),document_id):
        notify_version_changed(v['version_id'])
    return redirect(url_for('review_options.settings_page',document_id=document_id),303)


@bp.route('/api/documents/<document_id>/viewer-preferences',methods=['GET','POST','DELETE'])
@guarded
def viewer_preferences(document_id):
    if request.method=='GET':
        values=preferences.read_preferences(database_path(),document_id,actor())
    else:
        payload=json_payload(32768)
        if request.method=='DELETE':
            exact_fields(payload,set())
        values=preferences.save_preferences(database_path(),document_id,actor(),payload,reset=request.method=='DELETE')
    return jsonify(preferences=values)


@bp.post('/account/review-color')
@guarded
def color():
    if set(request.form)-{'csrf_token','review_color'}:
        abort(400)
    preferences.save_color(database_path(),actor(),request.form.get('review_color'))
    notify_user_presentation_changed(actor())
    return redirect(url_for('accounts.account'),303)


@bp.get('/api/versions/<version_id>/review-context')
@guarded
def context(version_id):
    version=get_version(database_path(),version_id)
    return jsonify(preferences=preferences.read_preferences(database_path(),version['document_id'],actor()),
        people=preferences.people(database_path(),version['document_id'],actor(),version_id),
        sections=sections.list_sections(database_path(),version['document_id'],version_id),
        responses=section_feedback.list_responses(database_path(),version_id,actor()))


@bp.get('/documents/<document_id>/sections')
@guarded
def sections_page(document_id):
    versions=list_versions(database_path(),document_id)
    version_id=request.args.get('version') or (versions[0]['version_id'] if versions else None)
    if version_id and not any(v['version_id']==version_id for v in versions):
        abort(404)
    return render_template('sections.html',document=get_document(database_path(),document_id),versions=versions,
        version_id=version_id,sections=sections.list_sections(database_path(),document_id,version_id))


@bp.post('/api/documents/<document_id>/sections')
@guarded
def create_section(document_id):
    section_id=sections.create_section(database_path(),document_id,actor(),json_payload(8192))
    changed(document_id)
    return jsonify(section_id=section_id),201


@bp.patch('/api/sections/<section_id>')
@guarded
def section_update(section_id):
    sections.update_section(database_path(),section_id,actor(),json_payload(8192))
    from .auth import resource_document
    changed(resource_document({'section_id':section_id}))
    return jsonify(ok=True)


@bp.post('/api/versions/<version_id>/sections/<section_id>/placement')
@guarded
def placement(version_id,section_id):
    sections.save_placement(database_path(),section_id,version_id,actor(),json_payload(8192))
    notify_version_changed(version_id)
    return jsonify(ok=True)


@bp.post('/api/versions/<version_id>/sections/outline')
@guarded
def outline(version_id):
    payload=json_payload(256*1024)
    exact_fields(payload,{'candidates'})
    document_id=get_version(database_path(),version_id)['document_id']
    sections.import_outline(database_path(),document_id,version_id,actor(),payload['candidates'])
    changed(document_id)
    return jsonify(ok=True),201


@bp.post('/api/versions/<version_id>/sections/<section_id>/responses')
@guarded
def response_create(version_id,section_id):
    payload=json_payload(16*1024)
    exact_fields(payload,{'body'})
    response_id=section_feedback.create_response(database_path(),section_id,version_id,actor(),payload['body'])
    notify_version_changed(version_id)
    return jsonify(response_id=response_id),201


@bp.post('/api/section-responses/<response_id>/comments')
@guarded
def response_reply(response_id):
    payload=json_payload(16*1024)
    exact_fields(payload,{'body'})
    version_id=section_feedback.reply(database_path(),response_id,actor(),payload['body'])
    notify_version_changed(version_id)
    return jsonify(ok=True)


@bp.route('/api/section-comments/<section_comment_id>',methods=['PATCH','DELETE'])
@guarded
def response_comment(section_comment_id):
    if request.method=='DELETE':
        values={'delete':True}
    else:
        values=json_payload(16*1024)
        exact_fields(values,{'body','expected_revision'})
    version_id=section_feedback.change_comment(database_path(),section_comment_id,actor(),**values)
    notify_version_changed(version_id)
    return jsonify(ok=True)


def changed(document_id):
    for version in list_versions(database_path(),document_id):
        notify_version_changed(version['version_id'])
