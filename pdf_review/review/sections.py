"""Flat logical sections and explicitly confirmed PDF-space version placements."""

import json
import math
from uuid import uuid4

from .access import authorize_actor
from .database import connect, transaction
from .documents import now_utc


class SectionError(ValueError):
    pass


class SectionConflict(SectionError):
    pass


def text(value, maximum, *, required=False):
    if not isinstance(value,str) or len(value)>maximum or (required and not value.strip()):
        raise SectionError('Invalid section name or prompt.')
    return value.strip()


def sections_in_connection(c,document_id,version_id=None,*,archived=False):
    rows = c.execute('''SELECT s.*,p.start_page,p.start_y,p.end_page,p.end_y,
        p.start_view_box,p.end_view_box,p.revision FROM sections s
        LEFT JOIN section_placements p ON p.section_id=s.section_id AND p.version_id=?
        WHERE s.document_id=? AND (? OR s.archived_at IS NULL) ORDER BY s.position,s.section_id''',
        (version_id,document_id,archived)).fetchall()
    result=[]
    for row in rows:
        item=dict(row)
        item['placement']=None if row['start_page'] is None else {k:item.pop(k) for k in
            ('start_page','start_y','end_page','end_y','start_view_box','end_view_box','revision')}
        if item['placement']:
            for key in ('start_view_box','end_view_box'):
                item['placement'][key]=json.loads(item['placement'][key])
        item['previous_placements']=[dict(r) for r in c.execute('''SELECT p.version_id,v.version_label,
            p.start_page,p.start_y,p.end_page,p.end_y FROM section_placements p
            JOIN document_versions v ON v.version_id=p.version_id WHERE p.section_id=? AND p.version_id!=?
            ORDER BY v.imported_at DESC''',(row['section_id'],version_id or ''))]
        result.append(item)
    return result


def list_sections(database,document_id,version_id=None):
    c=connect(database)
    try:
        return sections_in_connection(c,document_id,version_id)
    finally:
        c.close()


def _create(c,document_id,values):
    if set(values)-{'name','prompt','position','placement'}:
        raise SectionError('Unknown section field.')
    name=text(values.get('name'),200,required=True)
    prompt=text(values.get('prompt',''),2000)
    position=values.get('position', c.execute('SELECT COALESCE(MAX(position),-1)+1 FROM sections WHERE document_id=?',(document_id,)).fetchone()[0])
    if type(position) is not int or position<0:
        raise SectionError('Order must be a nonnegative integer.')
    section_id=str(uuid4())
    c.execute('INSERT INTO sections(section_id,document_id,name,position,prompt,created_at) VALUES(?,?,?,?,?,?)',
              (section_id,document_id,name,position,prompt,now_utc()))
    return section_id


def create_section(database,document_id,actor,values):
    with transaction(database) as c:
        authorize_actor(c,actor,document_id)
        if 'placement' in values:
            raise SectionError('Confirm placement separately in the viewer.')
        return _create(c,document_id,values)


def update_section(database,section_id,actor,values):
    if set(values)-{'name','prompt','position','archive'} or not values:
        raise SectionError('Unknown section field.')
    with transaction(database) as c:
        row=c.execute('SELECT * FROM sections WHERE section_id=? AND archived_at IS NULL',(section_id,)).fetchone()
        if not row:
            raise SectionError('Section not found.')
        authorize_actor(c,actor,row['document_id'])
        name=text(values.get('name',row['name']),200,required=True)
        prompt=text(values.get('prompt',row['prompt']),2000)
        position=values.get('position',row['position'])
        if type(position) is not int or position<0 or type(values.get('archive',False)) is not bool:
            raise SectionError('Invalid section order or archive flag.')
        c.execute('UPDATE sections SET name=?,prompt=?,position=?,archived_at=? WHERE section_id=?',
                  (name,prompt,position,now_utc() if values.get('archive') else None,section_id))


def boundary(payload,kind):
    page=payload.get(kind+'_page')
    y=payload.get(kind+'_y')
    box=payload.get(kind+'_view_box')
    count=payload.get('page_count')
    if type(count) is not int or not 1<=count<=1_000_000 or type(page) is not int or not 1<=page<=count:
        raise SectionError('Boundary page is outside this PDF.')
    if not isinstance(box,list) or len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box) or box[2]<=box[0] or box[3]<=box[1]:
        raise SectionError('A canonical PDF view box is required.')
    if y is not None and (type(y) not in (int,float) or not math.isfinite(y) or not box[1]<=y<=box[3]):
        raise SectionError('Boundary Y is outside its PDF page.')
    return page,y,box


def location(page,y,box,kind):
    if y is None:
        return (page+(kind=='end'),0)
    # PDF y increases upward. Exact bottom is equal to the next page's top.
    fraction=(box[3]-y)/(box[3]-box[1])
    return (page+1,0) if fraction==1 else (page,fraction)


def _place(c,section_id,version_id,actor,payload):
    expected={'start_page','start_y','end_page','end_y','start_view_box','end_view_box','page_count','expected_revision'}
    if set(payload)!=expected:
        raise SectionError('Placement requires canonical start/end and expected_revision.')
    section=c.execute('SELECT * FROM sections WHERE section_id=? AND archived_at IS NULL',(section_id,)).fetchone()
    version=c.execute('SELECT document_id FROM document_versions WHERE version_id=?',(version_id,)).fetchone()
    if not section or not version or section['document_id']!=version[0]:
        raise SectionError('Section and version must belong to the same document.')
    authorize_actor(c,actor,section['document_id'])
    old=c.execute('SELECT revision FROM section_placements WHERE section_id=? AND version_id=?',(section_id,version_id)).fetchone()
    revision=old[0] if old else 0
    if type(payload['expected_revision']) is not int or payload['expected_revision']!=revision:
        raise SectionConflict('Placement changed. Refresh before saving.')
    start_page,start_y,start_box=boundary(payload,'start')
    end_page,end_y,end_box=boundary(payload,'end')
    start=location(start_page,start_y,start_box,'start')
    end=location(end_page,end_y,end_box,'end')
    if start>=end:
        raise SectionError('Section end must follow its start.')
    for row in c.execute('''SELECT p.* FROM section_placements p JOIN sections s USING(section_id)
            WHERE p.version_id=? AND p.section_id!=? AND s.archived_at IS NULL''',(version_id,section_id)):
        other_start=location(row['start_page'],row['start_y'],json.loads(row['start_view_box']),'start')
        other_end=location(row['end_page'],row['end_y'],json.loads(row['end_view_box']),'end')
        if start<other_end and other_start<end:
            raise SectionError('Section ranges must not overlap.')
    c.execute('''INSERT INTO section_placements VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(section_id,version_id) DO UPDATE SET start_page=excluded.start_page,start_y=excluded.start_y,
        end_page=excluded.end_page,end_y=excluded.end_y,start_view_box=excluded.start_view_box,
        end_view_box=excluded.end_view_box,revision=excluded.revision,updated_by=excluded.updated_by,updated_at=excluded.updated_at''',
        (section_id,version_id,start_page,start_y,end_page,end_y,json.dumps(start_box),json.dumps(end_box),revision+1,actor,now_utc()))


def save_placement(database,section_id,version_id,actor,payload):
    with transaction(database) as c:
        _place(c,section_id,version_id,actor,payload)


def import_outline(database,document_id,version_id,actor,candidates):
    if not isinstance(candidates,list) or not 1<=len(candidates)<=200:
        raise SectionError('Select between 1 and 200 outline candidates.')
    with transaction(database) as c:
        authorize_actor(c,actor,document_id)
        for candidate in candidates:
            if not isinstance(candidate,dict) or set(candidate)!={'name','prompt','placement'}:
                raise SectionError('Invalid confirmed outline candidate.')
            section_id=_create(c,document_id,candidate)
            _place(c,section_id,version_id,actor,candidate['placement'])
