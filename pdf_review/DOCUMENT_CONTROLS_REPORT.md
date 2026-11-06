# Document controls, main version and homepage owners

Follow-up: a green owner-only **Share** button opens the shared native dialog.
Existing-member and email forms share one Jinja fragment with Manage access;
submissions return inline confirmation or a copyable invitation link. Error
retries preserve input. The same owner/trust/CSRF services apply, including the
fragment load. No migration is added. The focused browser check
`tests/browser_sanity.py --share-dialog` passes desktop/mobile bounds, native
focus/Escape, in-place grant, failed request/retry, invitation link output and
owner-only visibility. Its synthetic screenshots were visually inspected.

Implemented locally November 5, 2026. Existing staged invitation changes and the
user's unstaged login/root documentation edits were preserved. No real runtime
database, server, deployment, credentials or manuscript was touched.

- Manage access is a direct owner-only button beside Document actions.
- Document actions > Delete version opens a canonical nested version picker
  with filenames, labels/import dates and the main-version marker. Selection
  opens the existing exact-version confirmation; GET never deletes content.
- Verify integrity sits immediately left of Open PDF. The pair stays together
  when controls wrap on a narrow screen. Version cards retain metadata and hashes.
- Owners get a Make main version toggle. Exactly one version is marked while
  active versions exist; selecting the current main is idempotent. Other readers
  receive a visible badge without a mutation control.
- Homepage rows include all current document owners' display names. They expose
  no owner emails or unrelated documents; existing dashboard refresh also updates
  these labels.

Migration 15 adds a document_main_versions table with document/version foreign
keys and active/same-document validation triggers. Existing documents default to
the newest active version. New documents initialize on their first import;
later imports preserve the selection. Deleting the main version selects the
newest surviving version, or clears the designation for an empty document.
The change/fallback and access audit commit atomically. The explicit main-version
POST is owner-only, CSRF-protected and reauthorizes inside its write transaction.
Immutable PDF/version identities and previous migrations remain unchanged.

Back up real SQLite before normal startup applies migration 15. No manual data
operation or server restart was performed by this task. Main-version labels on
another already-open document page update on its next load; no new realtime
protocol was introduced.

Validation covers main selection, persistence/idempotence, immutable version rows,
authorization/CSRF/forged fields, withdrawn and cross-document rejection, database
triggers, first-import behavior, deletion fallback/last-version handling, audit
rollback, accessible owner labels, and a repeated populated migration-14 upgrade.
The focused browser check exercises desktop/tablet/mobile menu bounds, integrity
and Open PDF placement, persistent single selection after reload and owner names.
The existing version-deletion browser check passes the relocated picker,
confirmation/cancel, live viewer retirement and final empty-document state.
Synthetic rendered desktop/mobile pages were opened and inspected. Screenshots
remain ignored in tests/visual-artifacts. No production Google or physical-device
validation is claimed. The login regression assertion was updated to preserve
the user's existing shorter login wording and continue checking both policy links.

Final results: all **218 unit/security tests passed**, both focused browser checks
passed, and Git whitespace checks passed.

Commands:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -q
.venv/Scripts/python.exe tests/browser_sanity.py --document-controls
.venv/Scripts/python.exe tests/browser_sanity.py --version-delete
```
