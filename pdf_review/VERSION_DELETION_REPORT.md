# Delete a document version

Document owners now have **Delete version** beside each version on the document
page. GET opens a confirmation showing its filename, label and import date; Cancel
makes no change. The confirmed POST removes exactly that version from normal use.
Readers/reviewers do not see the control and cannot use either route. Deleting the
last version keeps the document and its upload form.

Deletion is an application withdrawal: version PDF/view/review/reading links stop
working, version lists/counts omit it, and live viewers return to the document.
It retains immutable PDF bytes and historical review records internally, as stated
in the confirmation. No files are erased, including deduplicated/shared blobs.
No uploaded user version was deleted while implementing or testing this feature.
Re-importing the same bytes creates a fresh active version ID.

Migration 13 adds only `version_deletions` (version, author, date) and the
`active_document_versions` view. The ledger is append-only. Original version
identity, checksum/path, anchors, conversations, revisions, section responses,
reading history and migration records stay intact. Lists/resource resolution and
transactional version services use the active view. The `version_table` helper
keeps historical pre-migration offline imports/test fixtures working until their
normal migration pass creates that view.

A conversation carried to another surviving version remains there with its original
identity and comments. Deleted-version anchors/targets and conversations without a
live target are unavailable through normal APIs. Carry-forward runs involving a
withdrawn version are hidden from normal lists and blocked from further decisions;
their stored provenance is retained. Section conversations on that version and
reading writes are also blocked. Only that version's current reading leases are
released, never another document/version's lease.

The service rechecks active document ownership inside its transaction, validates
confirmation against the route's exact version ID, inserts the withdrawal ledger,
appends a `version.delete` audit record, and releases leases together. HTTP enforces
owner access and CSRF; body-supplied user identities are not accepted. Repeated
service deletion is idempotent; deleted-version HTTP links return 404. After commit,
`review.version_deleted` sends no actor/content metadata and retires the room.
Eligible connected viewers disconnect and return to the document. Already downloaded
PDF bytes cannot be recalled from a browser.

Files: `review/migration13.sql`, `database.py`, `documents.py`, `auth.py`, `routes.py`,
version-scoped review/reading/section/migration services and `realtime.py`;
`templates/{document,delete_version}.html`, `static/styles/base.css`, and the existing
viewer realtime listener/integration. No restore/purge page or filesystem cleanup
mechanism is introduced.

Verification:

- All **180 unit/security tests passed**, including six focused deletion cases:
  permissions/CSRF/confirmation, active reads/list counts, shared blobs and last
  version/re-import, retained/carried feedback and stale reading writes, live rooms,
  ownership changes, idempotence/audit and immutable ledger triggers.
- `tests/browser_sanity.py --version-delete` passed: confirmation/cancel, exact
  version removal, reviewer controls, live second-viewer redirect, old PDF 404,
  surviving version links and the empty document/upload state. Rendered confirmation
  and result screenshots were inspected in ignored visual artifacts.
- The local database received a verified SQLite online backup before migration 13.
  After restarting, quick-check and foreign keys pass; earlier migration records
  and every original version row match the backup. `version_deletions` is empty:
  no real version was removed. The normal .env is unchanged.

Local app: http://127.0.0.1:5000/. Public tunnel remains stopped. No staging, commit,
push, SSH or production deployment was performed.
