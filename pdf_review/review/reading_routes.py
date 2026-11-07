"""Explicit ACL/CSRF-protected reading APIs; server session supplies the actor."""
from functools import wraps
from flask import Blueprint, abort, g, jsonify, request
from . import reading
from .access import AccessDenied
from .realtime import notify_reading_changed

def notify_reading_policy(version_id):
    from .documents import get_version, list_versions
    version=get_version(database_path(),version_id)
    for item in list_versions(database_path(),version["document_id"]):
        notify_reading_changed(item["version_id"])

from .routes import database_path, json_payload, ApiPayloadError, api_error

bp = Blueprint('reading', __name__)


def guarded(fn):
    @wraps(fn)
    def call(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except AccessDenied:
            abort(403)
        except LookupError:
            abort(404)
        except ApiPayloadError as error:
            return api_error(error.code, str(error), error.status)
        except (reading.ReadingError, ValueError, TypeError) as error:
            return api_error('invalid_reading_activity', str(error), 422)
    return call


@bp.get('/api/versions/<version_id>/reading')
@guarded
def summary(version_id):
    offset = reading.integer(int(request.args.get('offset', 0)), 0, 1000000)
    return jsonify(reading.reading_summary(database_path(), version_id, g.auth_user['user_id'], offset))


@bp.post('/api/versions/<version_id>/reading/consent')
@guarded
def consent(version_id):
    payload = json_payload(2048)
    if set(payload) - {'action', 'page_count', 'reader_id'} or not {'action','page_count'} <= set(payload):
        raise reading.ReadingError('Invalid consent fields.')
    result = reading.change_consent(database_path(), version_id, g.auth_user['user_id'], **payload)
    notify_reading_policy(version_id)
    return jsonify(tracking=result)


@bp.post('/api/versions/<version_id>/reading/sessions')
@guarded
def session(version_id):
    payload = json_payload(1024)
    if set(payload) != {'generation','page_count'}:
        raise reading.ReadingError('Invalid session fields.')
    reading.integer(payload['generation'], 1, 1000000000)
    return jsonify(reading.start_session(database_path(), version_id, g.auth_user['user_id'], payload['generation'],payload['page_count']))


@bp.post('/api/versions/<version_id>/reading/batches')
@guarded
def batch(version_id):
    result=reading.record_batch(database_path(), version_id, g.auth_user['user_id'], json_payload(16384))
    if not result['duplicate']:
        notify_reading_changed(version_id,g.auth_user['user_id'])
    return jsonify(result)


@bp.get('/api/versions/<version_id>/reading/readers/<reader_id>')
@guarded
def reader(version_id, reader_id):
    return jsonify(reading.reader_detail(database_path(), version_id, g.auth_user['user_id'], reader_id,
                                         int(request.args.get('start', 1)), int(request.args.get('limit', 50)),
                                         pages_only=request.args.get('pages_only')=='1'))


@bp.route('/api/versions/<version_id>/page-properties', methods=['GET', 'POST'])
@guarded
def properties(version_id):
    from . import page_properties
    if request.method == 'POST':
        return jsonify(page_properties.save(database_path(), version_id, g.auth_user['user_id'], json_payload(1048576)))
    return jsonify(page_properties.cached(database_path(), version_id, g.auth_user['user_id'], int(request.args.get('after', 0))))
