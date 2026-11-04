"""Author-controlled exact-version viewing estimates, separate from ephemeral presence.

Timing and word counts are browser observations, never evidence of comprehension.
Receipt windows and a per-user lease bound accepted time across all tabs/devices.
"""
import json
import math
import time
from datetime import datetime, timezone
from uuid import uuid4

from .access import AccessDenied, ELIGIBLE
from .database import connect, transaction
from .documents import now_utc
from .review_policy import require_reader

WORDS_PER_MINUTE = 400
MIN_PAGE_SECONDS = 5
BATCH_SECONDS = 15
LEASE_SECONDS = 25
IDLE_SECONDS = 60
MAX_BATCH_MS = 20000


class ReadingError(ValueError):
    pass


def policy():
    return dict(words_per_minute=WORDS_PER_MINUTE, minimum_page_seconds=MIN_PAGE_SECONDS,
                batch_seconds=BATCH_SECONDS, lease_seconds=LEASE_SECONDS, idle_seconds=IDLE_SECONDS)


def threshold_ms(words):
    return max(MIN_PAGE_SECONDS * 1000, math.ceil(words * 60000 / WORDS_PER_MINUTE))


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ReadingError('Invalid reading activity number.')
    return value


def version_reader(c, version_id, user_id):
    version = c.execute('SELECT document_id FROM document_versions WHERE version_id=?', (version_id,)).fetchone()
    if not version:
        raise LookupError()
    return version['document_id'], require_reader(c, version['document_id'], user_id)


def consent(c, version_id, user_id):
    row = c.execute('SELECT * FROM reading_consents WHERE version_id=? AND user_id=?', (version_id, user_id)).fetchone()
    state = dict(row) if row else dict(generation=1, consented_at=None, page_count=None)
    document = c.execute('SELECT document_id FROM document_versions WHERE version_id=?',(version_id,)).fetchone()[0]
    from .review_policy import settings
    enabled = settings(c, document)['reading_tracking_enabled']
    paused = c.execute('SELECT 1 FROM document_reading_pauses WHERE document_id=? AND user_id=?',(document,user_id)).fetchone()
    state['status'] = 'off' if not enabled else 'paused' if paused else 'active'
    return state


def change_consent(database, version_id, user_id, action, page_count, reader_id=None):
    """Legacy URL, now strictly author-only document policy; no personal opt-out."""
    if action not in ('enable', 'pause'):
        raise ReadingError('Choose enable or pause.')
    integer(page_count, 1, 100000)
    if reader_id is not None and (not isinstance(reader_id,str) or not 1 <= len(reader_id) <= 128):
        raise ReadingError('Invalid reader.')
    from .preferences import save_defaults
    c = connect(database)
    try:
        document, role = version_reader(c, version_id, user_id)
        require_reader(c, document, user_id, owner=True)
        target = reader_id or user_id
        require_reader(c, document, target)
    finally:
        c.close()
    save_defaults(database, document, user_id, {}, {target:int(action == 'pause')})
    c = connect(database)
    try:
        return consent(c, version_id, target)
    finally:
        c.close()


def start_session(database, version_id, user_id, generation, page_count=None):
    with transaction(database) as c:
        version_reader(c, version_id, user_id)
        state = consent(c, version_id, user_id)
        if state['status'] != 'active' or generation != state['generation']:
            raise ReadingError('Author tracking settings changed. Refresh reading progress.')
        if page_count is not None:
            integer(page_count, 1, 100000)
            if state['page_count'] and state['page_count'] != page_count:
                raise ReadingError('Page count differs from the registered exact PDF version.')
        count = state['page_count'] or page_count
        if not count:
            raise ReadingError('Page count is required to start tracking.')
        sid, stamp = str(uuid4()), now_utc()
        c.execute("""INSERT INTO reading_consents VALUES(?,?,'active',?,?,?,?)
            ON CONFLICT(version_id,user_id) DO UPDATE SET consented_at=coalesce(reading_consents.consented_at,excluded.consented_at)""",
                  (version_id,user_id,generation,count,stamp,stamp))
        c.execute('INSERT INTO reading_sessions VALUES(?,?,?,?,0,?,?)', (sid, version_id, user_id, generation, stamp, stamp))
        return dict(session_id=sid, sequence=0)


def record_batch(database, version_id, user_id, payload, *, clock=None):
    allowed = {'session_id', 'sequence', 'active', 'current_page', 'pages'}
    if set(payload) != allowed or type(payload['active']) is not bool:
        raise ReadingError('Invalid reading batch fields.')
    seq = integer(payload['sequence'], 1, 1000000000)
    items = payload['pages']
    if not isinstance(items, list) or len(items) > 32:
        raise ReadingError('Reading batch is too large.')
    if not isinstance(payload['session_id'], str) or len(payload['session_id']) > 80:
        raise ReadingError('Invalid session.')
    now = time.time() if clock is None else clock
    stamp = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    with transaction(database) as c:
        version_reader(c, version_id, user_id)
        state = consent(c, version_id, user_id)
        session = c.execute('SELECT * FROM reading_sessions WHERE session_id=? AND version_id=? AND user_id=?',
                            (payload['session_id'], version_id, user_id)).fetchone()
        if not session or state['status'] != 'active' or session['generation'] != state['generation']:
            raise ReadingError('Author tracking settings changed.')
        lease = c.execute('SELECT * FROM reading_leases WHERE user_id=?', (user_id,)).fetchone()
        owns = bool(lease and lease['session_id'] == session['session_id'] and lease['expires_at'] >= now)
        if seq <= session['last_seq']:
            return dict(sequence=seq, granted=owns, accepted_ms=0, duplicate=True)
        if seq != session['last_seq'] + 1:
            raise ReadingError('Reading batches must be acknowledged in order.')
        current = payload['current_page']
        if current is not None:
            integer(current, 1, state['page_count'])
        requested, normalized = 0, []
        seen = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != {'page', 'ms', 'visit', 'words'}:
                raise ReadingError('Invalid page activity fields.')
            page = integer(item['page'], 1, state['page_count'])
            visit = integer(item['visit'], 1, 1000000000)
            ms = integer(item['ms'], 1, MAX_BATCH_MS)
            words = item['words']
            if words is not None:
                integer(words, 0, 100000)
            if (page, visit) in seen:
                raise ReadingError('Duplicate page visit in batch.')
            seen.add((page, visit))
            requested += ms
            normalized.append((page, visit, ms, words))
        budget = min(MAX_BATCH_MS, max(0, int((now - lease['received_at']) * 1000))) if owns else 0
        factor = min(1, budget / requested) if requested else 0
        accepted, new_pages, new_read, furthest = 0, 0, 0, 0
        for page, visit, ms, words in normalized:
            amount = math.floor(ms * factor)
            if amount <= 0:
                continue
            old = c.execute('SELECT * FROM reading_pages WHERE version_id=? AND user_id=? AND page_number=?', (version_id, user_id, page)).fetchone()
            total = (old['active_ms'] if old else 0) + amount
            word_count = old['word_count'] if old and old['word_count'] is not None else words
            read_at = old['read_at'] if old else None
            if read_at is None and word_count is not None and total >= threshold_ms(word_count):
                read_at = stamp
                new_read += 1
            first = old['first_visited'] if old else stamp
            inserted = c.execute('''INSERT OR IGNORE INTO reading_visits VALUES(?,?,?,?,?,?)''',
                                 (session['session_id'], visit, page, stamp, stamp, 0)).rowcount
            c.execute('UPDATE reading_visits SET active_ms=active_ms+?,last_visited=? WHERE session_id=? AND visit_index=? AND page_number=?',
                      (amount, stamp, session['session_id'], visit, page))
            c.execute('''INSERT INTO reading_pages VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(version_id,user_id,page_number) DO UPDATE SET word_count=excluded.word_count,
                active_ms=excluded.active_ms,last_visited=excluded.last_visited,read_at=excluded.read_at,visit_count=excluded.visit_count''',
                      (version_id, user_id, page, word_count, total, first, stamp, read_at,
                       (old['visit_count'] if old else 0) + inserted))
            accepted += amount
            new_pages += int(old is None)
            furthest = max(furthest, page)
        if accepted:
            c.execute('''INSERT INTO reading_totals(version_id,user_id,active_ms,pages_visited,pages_read,furthest_page,last_page,first_activity,last_activity)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(version_id,user_id) DO UPDATE SET
                active_ms=active_ms+excluded.active_ms,pages_visited=pages_visited+excluded.pages_visited,
                pages_read=pages_read+excluded.pages_read,furthest_page=max(furthest_page,excluded.furthest_page),
                last_page=excluded.last_page,last_activity=excluded.last_activity''',
                      (version_id, user_id, accepted, new_pages, new_read, furthest, current or furthest, stamp, stamp))
        granted = bool(payload['active'] and (owns or not lease or lease['expires_at'] < now))
        if granted:
            c.execute('''INSERT INTO reading_leases VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
                session_id=excluded.session_id,received_at=excluded.received_at,expires_at=excluded.expires_at,current_page=excluded.current_page''',
                      (user_id, session['session_id'], now, now + LEASE_SECONDS, current))
        elif lease and lease['session_id'] == session['session_id']:
            # Retain the receipt watermark while releasing ownership; a successor
            # acquires with an empty batch and cannot backfill the previous time.
            c.execute('UPDATE reading_leases SET received_at=?,expires_at=?,current_page=NULL WHERE user_id=?', (now, now - .001, user_id))
        c.execute('UPDATE reading_sessions SET last_seq=?,updated_at=? WHERE session_id=?', (seq, stamp, session['session_id']))
        return dict(sequence=seq, granted=granted, accepted_ms=accepted, duplicate=False)


def section_ranges(c, version_id):
    rows = c.execute('''SELECT s.section_id,s.name,p.start_page,p.end_page,p.start_y,p.end_y,p.start_view_box,p.end_view_box
        FROM section_placements p JOIN sections s USING(section_id)
        WHERE p.version_id=? AND s.archived_at IS NULL ORDER BY p.start_page,s.position''', (version_id,)).fetchall()
    result = []
    for row in rows:
        def coordinate(kind):
            box = json.loads(row[kind + '_view_box'])
            fraction = (box[3] - row[kind + '_y']) / (box[3] - box[1]) if row[kind + '_y'] is not None else int(kind == 'end')
            return row[kind + '_page'] - 1 + min(1, max(0, fraction))
        start, end = coordinate('start'), coordinate('end')
        result.append(dict(section_id=row['section_id'], name=row['name'], start=start, end=end,
                           start_page=math.floor(start) + 1, end_page=math.ceil(end)))
    return result


def reading_summary(database, version_id, user_id, offset=0):
    c = connect(database)
    try:
        document_id, role = version_reader(c, version_id, user_id)
        own = consent(c, version_id, user_id)
        # Reading analytics are stricter than shared review: other readers are
        # never disclosed to non-owners, regardless of personal comment filters.
        rows = c.execute('''SELECT u.user_id,u.display_name,u.review_color,CASE WHEN coalesce(ds.reading_tracking_enabled,1)=0 THEN 'off' WHEN rp.user_id IS NOT NULL THEN 'paused' ELSE 'active' END status,r.page_count,
            coalesce(t.active_ms,0) active_ms,coalesce(t.pages_read,0) pages_read,
            coalesce(t.pages_visited,0) pages_visited,coalesce(t.furthest_page,0) furthest_page,
            t.last_page,t.last_activity,l.current_page,
            (l.expires_at>? AND rs.version_id=? AND r.status='active') online
            FROM reading_consents r JOIN users u USING(user_id)
            JOIN document_access a ON a.user_id=u.user_id AND a.document_id=(SELECT document_id FROM document_versions WHERE version_id=?)
            LEFT JOIN document_review_settings ds ON ds.document_id=a.document_id
            LEFT JOIN document_reading_pauses rp ON rp.document_id=a.document_id AND rp.user_id=r.user_id
            LEFT JOIN reading_totals t ON t.version_id=r.version_id AND t.user_id=r.user_id
            LEFT JOIN reading_leases l ON l.user_id=r.user_id
            LEFT JOIN reading_sessions rs ON rs.session_id=l.session_id
            WHERE r.version_id=? AND r.consented_at IS NOT NULL AND (? OR r.user_id=?)
            AND u.user_id IN (SELECT u.user_id FROM users u JOIN allowed_emails e ON e.normalized_email=u.normalized_email
                WHERE u.is_active=1 AND u.email_verified=1 AND u.google_subject IS NOT NULL AND e.enabled=1)
            ORDER BY u.display_name COLLATE NOCASE,u.user_id LIMIT 101 OFFSET ?''',
                         (time.time(), version_id, version_id, version_id, int(role == 'owner'), user_id, offset)).fetchall()
        readers = [dict(r) for r in rows[:100]]
        for reader in readers:
            reader['online'] = reader['online'] and reader['status'] == 'active'
            reader['current_page'] = reader['current_page'] if reader['online'] else None
            reader['online'] = bool(reader['online'])
        from .review_policy import settings
        return dict(tracking=own, document_tracking_enabled=bool(settings(c,document_id)['reading_tracking_enabled']), policy=policy(), readers=readers, sections=section_ranges(c, version_id),
                    next_offset=offset + 100 if len(rows) > 100 else None)
    finally:
        c.close()


def reader_detail(database, version_id, actor, reader, start=1, limit=50, *, pages_only=False):
    integer(start, 1, 100000)
    integer(limit, 1, 100)
    c = connect(database)
    try:
        document_id, role = version_reader(c, version_id, actor)
        if reader != actor and role != 'owner':
            raise AccessDenied('Only your own reading activity is available.')
        require_reader(c, document_id, reader)
        state = consent(c, version_id, reader)
        if not state['consented_at']:
            raise LookupError()
        count = state['page_count']
        # Indexed page window; the detailed card never downloads a long PDF's
        # whole per-page or visit history merely to display its first screen.
        rows = {r['page_number']: dict(r) for r in c.execute('SELECT * FROM reading_pages WHERE version_id=? AND user_id=? AND page_number>=? AND page_number<?',
                 (version_id, reader, start, min(count + 1, start + limit)))}
        pages = []
        for page in range(start, min(count + 1, start + limit)):
            row = rows.get(page, dict(page_number=page, active_ms=0, word_count=None, first_visited=None, last_visited=None, read_at=None, visit_count=0))
            row = {k:v for k,v in row.items() if k not in ('version_id','user_id')}
            row['threshold_ms'] = threshold_ms(row['word_count']) if row['word_count'] is not None else None
            row['state'] = 'read' if row['read_at'] else 'partial' if row['active_ms'] else 'unread'
            row['long_dwell'] = bool(row['threshold_ms'] and row['active_ms'] > max(120000, row['threshold_ms'] * 3))
            pages.append(row)
        if pages_only:
            return dict(reader_id=reader,page_count=count,pages=pages,
                        next_page=start+limit if start+limit<=count else None)
        # Prefix sums over visited pages let each section use two indexed binary
        # searches rather than repeatedly scanning all pages/visits.
        from bisect import bisect_left
        all_pages = c.execute('SELECT page_number,active_ms,read_at FROM reading_pages WHERE version_id=? AND user_id=? ORDER BY page_number', (version_id, reader)).fetchall()
        numbers, times, reads = [], [0], [0]
        by_page = {}
        for page in all_pages:
            numbers.append(page['page_number'])
            times.append(times[-1] + page['active_ms'])
            reads.append(reads[-1] + int(bool(page['read_at'])))
            by_page[page['page_number']] = page
        sections = section_ranges(c, version_id)
        for section in sections:
            lo, hi = max(0, section['start']), min(count, section['end'])
            first, last = math.floor(lo) + 1, math.ceil(hi)
            a, b = bisect_left(numbers, first), bisect_left(numbers, last + 1)
            active, completed = times[b] - times[a], reads[b] - reads[a]
            for number in {first, last}:
                overlap = max(0, min(hi, number) - max(lo, number - 1))
                row = by_page.get(number)
                if row:
                    active -= (1 - overlap) * row['active_ms']
                    completed -= (1 - overlap) * int(bool(row['read_at']))
            section.update(active_ms=round(max(0, active)), pages_read=round(max(0, completed), 2),
                           percentage=round(100 * max(0, completed) / (hi - lo), 1) if hi > lo else 0)
        total = c.execute('SELECT * FROM reading_totals WHERE version_id=? AND user_id=?', (version_id, reader)).fetchone()
        return dict(reader_id=reader, page_count=count, totals=dict(total) if total else {}, sections=sections,
                    pages=pages, next_page=start + limit if start + limit <= count else None)
    finally:
        c.close()
