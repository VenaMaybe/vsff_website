"""Reusable browser-derived PDF.js metrics; never text, activity, or PDF bytes.

Like observed reading word counts, these are client supplied estimates, not
trusted evidence. Successful first writes win; authorization is checked afresh.
"""
import json
import math

from .database import connect, transaction
from .reading import integer, version_reader, ReadingError


def cached(database, version, actor, after=0):
    integer(after, 0, 100000)
    c = connect(database)
    try:
        version_reader(c, version, actor)
        rows = c.execute('''SELECT page, page_count, metadata FROM version_text_properties
            WHERE version_id=? AND algorithm=2 AND page>? ORDER BY page LIMIT 50''', (version, after)).fetchall()
        return dict(rows=[dict(json.loads(r['metadata']), page_count=r['page_count']) for r in rows],
                    next=rows[-1]['page'] if len(rows) == 50 else None)
    finally:
        c.close()


def save(database, version, actor, payload):
    if set(payload) != {'page_count', 'rows'}:
        raise ReadingError('Invalid PDF text properties.')
    count = integer(payload['page_count'], 1, 100000)
    rows = payload['rows']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
        raise ReadingError('Invalid PDF text properties batch.')
    validated = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'page', 'words', 'area', 'wordRuns'}:
            raise ReadingError('Invalid PDF text properties row.')
        page = integer(row['page'], 1, count)
        words = integer(row['words'], 0, 10000000)
        area, runs = row['area'], row['wordRuns']
        if type(area) not in (int, float) or not math.isfinite(area) or not 0 < area <= 1e12:
            raise ReadingError('Invalid page area.')
        if not isinstance(runs, list) or len(runs) > 20000:
            raise ReadingError('Invalid word positions.')
        total = 0
        for run in runs:
            if (not isinstance(run, list) or len(run) != 2 or type(run[0]) not in (int, float)
                    or not math.isfinite(run[0]) or not 0 <= run[0] < 1):
                raise ReadingError('Invalid word position.')
            total += integer(run[1], 0, 10000000)
        if total != words:
            raise ReadingError('Word positions do not match the count.')
        validated.append((version, page, count, json.dumps(row, separators=(',', ':'))))
    with transaction(database) as c:
        version_reader(c, version, actor)
        c.executemany('''INSERT OR IGNORE INTO version_text_properties
            (version_id, algorithm, page, page_count, metadata) VALUES (?,2,?,?,?)''', validated)
    return dict(saved=True)
