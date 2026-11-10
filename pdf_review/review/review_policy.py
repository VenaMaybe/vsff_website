"""Review confidentiality and presentation filtering, applied before content reads."""

from .access import AccessDenied, ELIGIBLE
from .database import version_table


def require_reader(connection, document_id, user_id, *, write=False, owner=False):
    row = connection.execute('SELECT role FROM document_access WHERE document_id=? AND user_id=?',
                             (document_id, user_id)).fetchone()
    if not row or not connection.execute(ELIGIBLE + ' AND u.user_id=?', (user_id,)).fetchone():
        raise AccessDenied('Review access denied.')
    if (owner and row['role'] != 'owner') or (write and row['role'] == 'viewer'):
        raise AccessDenied('Review access denied.')
    return row['role']


def settings(connection, document_id):
    row = connection.execute('SELECT * FROM document_review_settings WHERE document_id=?', (document_id,)).fetchone()
    return dict(row) if row else dict(document_id=document_id, visibility_policy='shared',
        default_scope='all', default_spread=0, default_display='expanded', downloads_allowed=1, reading_tracking_enabled=1, section_prompts_in_compact=1)


def author_predicate(connection, document_id, user_id, author_column, *, personal=True):
    """Return trusted SQL and bound values; never fetch hidden conversations first."""
    role = require_reader(connection, document_id, user_id)
    policy = settings(connection, document_id)
    preference = connection.execute('SELECT scope FROM viewer_preferences WHERE document_id=? AND user_id=?',
                                    (document_id, user_id)).fetchone()
    scope = preference['scope'] if preference else policy['default_scope']
    if (policy['visibility_policy'] == 'isolated' and role != 'owner') or (personal and scope == 'mine'):
        return f'{author_column} = ?', [user_id]
    if personal:
        return f'''{author_column} NOT IN (SELECT hidden_user_id FROM hidden_reviewers
                   WHERE document_id=? AND user_id=?)''', [document_id, user_id]
    return '1=1', []


def thread_permitted(connection, thread_id, user_id):
    row = connection.execute('SELECT document_id FROM threads WHERE thread_id=?', (thread_id,)).fetchone()
    if not row:
        return False
    predicate, args = author_predicate(connection, row['document_id'], user_id, 't.created_by_user_id', personal=False)
    return bool(connection.execute(f'SELECT 1 FROM threads t WHERE t.thread_id=? AND {predicate} AND EXISTS(SELECT 1 FROM thread_target_heads h JOIN {version_table(connection)} v ON v.version_id=h.document_version_id WHERE h.thread_id=t.thread_id)',
                                  [thread_id, *args]).fetchone())
