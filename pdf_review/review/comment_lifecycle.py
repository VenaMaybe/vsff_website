"""Shared revision, conflict and tombstone operations for both conversation types.

Callers own BEGIN IMMEDIATE, conversation authorization and parent identity.
Table names come exclusively from the fixed families below.
"""

from uuid import uuid4

FAMILIES={'text':('comments','comment_revisions'), 'section':('section_comments','section_comment_revisions')}


def insert(c,family,parent_id,author,body,timestamp):
    from .threads import validate_comment_body
    body=validate_comment_body(body)
    table,revisions=FAMILIES[family]
    parent='thread_id' if family=='text' else 'response_id'
    comment_id=str(uuid4())
    c.execute(f'INSERT INTO {table}(comment_id,{parent},author_id,body,created_at) VALUES(?,?,?,?,?)',
              (comment_id,parent_id,author,body,timestamp))
    revision(c,family,comment_id,1,body,author,timestamp)
    return comment_id


def revision(c,family,comment_id,number,body,actor,timestamp):
    table=FAMILIES[family][1]
    c.execute(f'INSERT INTO {table}(revision_id,comment_id,revision_number,body,editor_id,created_at) VALUES(?,?,?,?,?,?)',
              (str(uuid4()),comment_id,number,body,actor,timestamp))


def change(c,family,comment_id,actor,timestamp,*,body=None,expected_revision=None,delete=False):
    from .threads import (CommentNotFoundError,CommentPermissionError,CommentConflictError,
                          ThreadValidationError,validate_comment_body)
    table,revisions=FAMILIES[family]
    row=c.execute(f'SELECT * FROM {table} WHERE comment_id=?',(comment_id,)).fetchone()
    if row is None:
        raise CommentNotFoundError('The comment does not exist.')
    if row['author_id']!=actor:
        raise CommentPermissionError('You can only change your own comments.')
    if delete:
        if row['deleted_at'] is None:
            c.execute(f'UPDATE {table} SET body=NULL,deleted_at=?,deleted_by_user_id=? WHERE comment_id=?',
                      (timestamp,actor,comment_id))
        return row
    body=validate_comment_body(body)
    if row['deleted_at'] is not None:
        raise ThreadValidationError('A deleted comment cannot be edited.')
    if type(expected_revision) is not int or expected_revision<1:
        raise ThreadValidationError('expected_revision must be a positive integer.')
    current=c.execute(f'SELECT MAX(revision_number) FROM {revisions} WHERE comment_id=?',(comment_id,)).fetchone()[0]
    if current!=expected_revision:
        raise CommentConflictError(current)
    if row['body']!=body:
        revision(c,family,comment_id,current+1,body,actor,timestamp)
        c.execute(f'UPDATE {table} SET body=?,edited_at=? WHERE comment_id=?',(body,timestamp,comment_id))
    return row
