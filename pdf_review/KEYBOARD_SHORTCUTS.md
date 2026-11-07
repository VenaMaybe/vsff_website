# Keyboard shortcuts

The maintained inventory is [review/shortcuts.py](review/shortcuts.py). Account
renders this list directly; update it whenever a supported keybind changes.
It includes application shortcuts and useful native PDF.js commands, with PDF
focus and download-policy restrictions noted. Browser/OS shortcuts and hidden
native editor/file-import actions are outside the application's supported list.

Handlers:

- `static/review/comment_navigation.js`: Shift+Down/Right next, Shift+Up/Left
  previous. Navigate authorized, filtered highlighted threads in page/text order,
  wrapping at both ends. The first keypress picks the highlight nearest the PDF
  viewport center unless the last selected thread still has a visible highlight;
  then advance from it. Test every rectangle/segment and both viewport axes.
  Clicks and keyboard navigation share the last-thread reference; deselecting a
  card does not discard it. Text selection, editing, menus and dialogs retain
  their own keyboard behavior. Section-response placeholders have no highlights
  and do not enter this cycle.
- `anchors.js`, `comment_composer.js`: selected-text commenting, Ctrl+Shift+Enter
  to submit new comments/replies/edits, and Escape.
- `viewer_shell.js`: pinned Ctrl/Command+F Search; Shift+Enter opens Tools from
  the document or Tools controls. Editors, Search and other controls retain their
  own Shift+Enter behavior.
- `menus.js`, `left_card.js`, section/statistics controls: focus navigation/Escape.
- Vendored `pdfjs/web/viewer.mjs` `onKeyDown`: PDF-focused native commands.
  Keep vendor unchanged. Do not claim Space temporarily pans; this viewer's
  native Space command scrolls or turns pages, depending on viewing mode.

Focused verification: `tests/browser_sanity.py --comment-navigation`.
