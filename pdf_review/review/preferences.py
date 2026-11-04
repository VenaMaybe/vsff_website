"""Document defaults and durable personal viewer choices; no authorization by color."""

from .access import authorize_actor, ELIGIBLE, AccessDenied
from .database import connect, transaction
from .review_policy import settings, require_reader, author_predicate


class PreferenceError(ValueError):
    pass


def validate(values, choices):
    if not isinstance(values, dict) or set(values) - set(choices):
        raise PreferenceError('Unknown setting.')
    for key, value in values.items():
        if type(value) not in (str, int) or value not in choices[key]:
            raise PreferenceError(f'Invalid {key}.')


DEFAULT_CHOICES = dict(visibility_policy=('shared','isolated'), default_scope=('all','mine'),
                       default_spread=(0,1,2), default_display=('expanded','minimized','hidden'), downloads_allowed=(0,1), reading_tracking_enabled=(0,1))
PERSONAL_CHOICES = dict(scope=('all','mine'), spread=(0,1,2), display=('expanded','minimized','hidden','mobile'))


def save_defaults(database, document_id, user_id, values, reader_pauses=None):
    validate(values, DEFAULT_CHOICES)
    with transaction(database) as c:
        authorize_actor(c, user_id, document_id)
        current = settings(c, document_id)
        pauses_changed = False
        if reader_pauses is not None:
            for reader, paused in reader_pauses.items():
                require_reader(c, document_id, reader)
                if paused not in (0, 1):
                    raise PreferenceError('Invalid reader tracking setting.')
                previous_pause = bool(c.execute('SELECT 1 FROM document_reading_pauses WHERE document_id=? AND user_id=?',(document_id,reader)).fetchone())
                pauses_changed |= previous_pause != bool(paused)
                if paused:
                    c.execute('INSERT OR IGNORE INTO document_reading_pauses VALUES(?,?)',(document_id,reader))
                else:
                    c.execute('DELETE FROM document_reading_pauses WHERE document_id=? AND user_id=?',(document_id,reader))
        policy_changed = ('reading_tracking_enabled' in values and values['reading_tracking_enabled'] != current['reading_tracking_enabled']) or pauses_changed
        if policy_changed:
            c.execute('UPDATE reading_consents SET generation=generation+1 WHERE version_id IN (SELECT version_id FROM document_versions WHERE document_id=?)',(document_id,))
            c.execute('DELETE FROM reading_leases WHERE session_id IN (SELECT s.session_id FROM reading_sessions s JOIN document_versions v USING(version_id) WHERE v.document_id=?)',(document_id,))
        current.update(values)
        c.execute('''INSERT INTO document_review_settings (document_id,visibility_policy,default_scope,default_spread,default_display,downloads_allowed,reading_tracking_enabled) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(document_id) DO UPDATE SET visibility_policy=excluded.visibility_policy,
            default_scope=excluded.default_scope,default_spread=excluded.default_spread,
            default_display=excluded.default_display,downloads_allowed=excluded.downloads_allowed,reading_tracking_enabled=excluded.reading_tracking_enabled''', tuple(current[k] for k in
            ('document_id','visibility_policy','default_scope','default_spread','default_display','downloads_allowed','reading_tracking_enabled')))


def read_preferences(database, document_id, user_id):
    c = connect(database)
    try:
        role = require_reader(c, document_id, user_id)
        defaults = settings(c, document_id)
        row = c.execute('SELECT scope,spread,display FROM viewer_preferences WHERE document_id=? AND user_id=?',
                        (document_id,user_id)).fetchone()
        values = dict(row) if row else dict(scope=defaults['default_scope'],spread=defaults['default_spread'],display=defaults['default_display'])
        hidden = [r[0] for r in c.execute('SELECT hidden_user_id FROM hidden_reviewers WHERE document_id=? AND user_id=?', (document_id,user_id))]
        enforced = defaults['visibility_policy'] == 'isolated' and role != 'owner'
        return dict(**values, hidden_reviewers=[] if enforced else hidden, initialized=bool(row), defaults=defaults,
                    isolated=enforced, effective_scope='mine' if enforced else values['scope'])
    finally:
        c.close()


def save_preferences(database, document_id, user_id, values, *, reset=False):
    values = dict(values)
    hidden = values.pop('hidden_reviewers', None)
    validate(values, PERSONAL_CHOICES)
    if hidden is not None and (not isinstance(hidden,list) or len(hidden)>200 or
            any(not isinstance(v,str) or len(v)>128 for v in hidden)):
        raise PreferenceError('Invalid people filter.')
    with transaction(database) as c:
        require_reader(c,document_id,user_id)
        defaults = settings(c,document_id)
        row = None if reset else c.execute('SELECT * FROM viewer_preferences WHERE document_id=? AND user_id=?',(document_id,user_id)).fetchone()
        current = dict(row) if row else dict(scope=defaults['default_scope'],spread=defaults['default_spread'],display=defaults['default_display'])
        current.update(values)
        c.execute('''INSERT INTO viewer_preferences VALUES(?,?,?,?,?) ON CONFLICT(document_id,user_id)
            DO UPDATE SET scope=excluded.scope,spread=excluded.spread,display=excluded.display''',
            (document_id,user_id,current['scope'],current['spread'],current['display']))
        if reset or hidden is not None:
            c.execute('DELETE FROM hidden_reviewers WHERE document_id=? AND user_id=?',(document_id,user_id))
        if hidden is not None:
            permitted = {u['user_id'] for u in people_in_connection(c,document_id,user_id)}
            if set(hidden)-permitted:
                raise PreferenceError('Only authors in this document may be filtered.')
            c.executemany('INSERT INTO hidden_reviewers VALUES(?,?,?)', [(document_id,user_id,u) for u in set(hidden)])
    return read_preferences(database,document_id,user_id)


def people_in_connection(c, document_id, user_id, version_id=None):
    predicate,args = author_predicate(c,document_id,user_id,'u.user_id',personal=False)
    # Only top-level content authors, never the beta directory or reply-only authors.
    return [dict(r) for r in c.execute(f'''SELECT u.user_id,u.display_name,u.review_color FROM users u
        WHERE {predicate} AND u.user_id IN (
          SELECT t.created_by_user_id FROM threads t JOIN thread_target_heads h ON h.thread_id=t.thread_id
          WHERE t.document_id=? AND (? IS NULL OR h.document_version_id=?)
          UNION SELECT r.author_id FROM section_responses r JOIN sections s ON s.section_id=r.section_id
          WHERE s.document_id=? AND (? IS NULL OR r.version_id=?)) ORDER BY u.display_name,u.user_id''',
        [*args,document_id,version_id,version_id,document_id,version_id,version_id])]


def people(database,document_id,user_id,version_id=None):
    c=connect(database)
    try:
        return people_in_connection(c,document_id,user_id,version_id)
    finally:
        c.close()


def palette(database):
    c=connect(database)
    try:
        return [r[0] for r in c.execute('SELECT color FROM review_palette ORDER BY rowid')]
    finally:
        c.close()


def save_color(database,user_id,color):
    with transaction(database) as c:
        if not c.execute(ELIGIBLE+' AND u.user_id=?',(user_id,)).fetchone():
            raise AccessDenied('Active account required.')
        if not isinstance(color,str) or not c.execute('SELECT 1 FROM review_palette WHERE color=?',(color,)).fetchone():
            raise PreferenceError('Choose a review palette color.')
        c.execute('UPDATE users SET review_color=? WHERE user_id=?',(color,user_id))
