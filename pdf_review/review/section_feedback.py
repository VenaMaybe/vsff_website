"""Exact-version section conversations, separate from immutable text anchors."""

from uuid import uuid4

from . import comment_lifecycle
from .database import version_table, connect,transaction
from .documents import now_utc
from .review_policy import author_predicate,require_reader
from .sections import SectionError


def permitted(c,response_id,user_id,*,write=False):
    row=c.execute(f'''SELECT r.*,s.document_id FROM section_responses r JOIN sections s USING(section_id) JOIN {version_table(c)} v ON v.version_id=r.version_id
                     WHERE response_id=?''',(response_id,)).fetchone()
    if row is None:
        return None
    require_reader(c,row['document_id'],user_id,write=write)
    clause,args=author_predicate(c,row['document_id'],user_id,'r.author_id',personal=False)
    if not c.execute(f'SELECT 1 FROM section_responses r WHERE response_id=? AND {clause}',[response_id,*args]).fetchone():
        return None
    return row


def list_responses(database,version_id,user_id):
    c=connect(database)
    try:
        c.execute('BEGIN')
        version=c.execute(f'SELECT document_id FROM {version_table(c)} WHERE version_id=?',(version_id,)).fetchone()
        if not version:
            raise SectionError('Version not found.')
        clause,args=author_predicate(c,version[0],user_id,'r.author_id')
        result=[]
        for row in c.execute(f'''SELECT r.*,u.display_name,u.review_color FROM section_responses r
                JOIN users u ON u.user_id=r.author_id WHERE r.version_id=? AND {clause}
                ORDER BY r.created_at,r.response_id''',[version_id,*args]).fetchall():
            response=dict(row)
            response['comments']=[dict(v) for v in c.execute('''SELECT c.*,u.display_name,u.review_color,
                (SELECT MAX(revision_number) FROM section_comment_revisions WHERE comment_id=c.comment_id) current_revision
                FROM section_comments c JOIN users u ON u.user_id=c.author_id
                WHERE c.response_id=? ORDER BY c.created_at,c.comment_id''',(row['response_id'],))]
            result.append(response)
        return result
    finally:
        c.close()


def create_response(database,section_id,version_id,user_id,body):
    with transaction(database) as c:
        row=c.execute('SELECT document_id FROM sections WHERE section_id=? AND archived_at IS NULL',(section_id,)).fetchone()
        if not row:
            raise SectionError('Section not found.')
        require_reader(c,row[0],user_id,write=True)
        if not c.execute(f'SELECT 1 FROM section_placements p JOIN {version_table(c)} v USING(version_id) WHERE p.section_id=? AND p.version_id=?',(section_id,version_id)).fetchone():
            raise SectionError('Section must be mapped on this version.')
        if c.execute('SELECT 1 FROM section_responses WHERE section_id=? AND version_id=? AND author_id=?',
                     (section_id,version_id,user_id)).fetchone():
            from .sections import SectionConflict
            raise SectionConflict('You already have a response here. Reply to or edit that conversation.')
        response_id=str(uuid4())
        c.execute('INSERT INTO section_responses VALUES(?,?,?,?,?)',(response_id,section_id,version_id,user_id,now_utc()))
        comment_lifecycle.insert(c,'section',response_id,user_id,body,now_utc())
    return response_id


def reply(database,response_id,user_id,body):
    with transaction(database) as c:
        row=permitted(c,response_id,user_id,write=True)
        if row is None:
            raise LookupError('Conversation not found.')
        comment_lifecycle.insert(c,'section',response_id,user_id,body,now_utc())
        return row['version_id']


def change_comment(database,comment_id,user_id,**values):
    with transaction(database) as c:
        row=c.execute('SELECT response_id FROM section_comments WHERE comment_id=?',(comment_id,)).fetchone()
        parent=permitted(c,row[0],user_id,write=True) if row else None
        if parent is None:
            raise LookupError('Comment not found.')
        comment_lifecycle.change(c,'section',comment_id,user_id,now_utc(),**values)
        return parent['version_id']
