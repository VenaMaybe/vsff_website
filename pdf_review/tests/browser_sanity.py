"""Optional Chrome sanity check, using DevTools directly (no browser framework).

Run from the project directory: python tests/browser_sanity.py
Uses isolated temporary PDFs/database/browser profiles, never the user's review data.
"""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def pdf_bytes(marker):
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>"]
    for page in [1, 2]:
        stream = f"BT /F1 16 Tf 60 500 Td (Review sentence {marker} page {page}.) Tj ET".encode()
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        if page == 1:
            objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    result = b"%PDF-1.4\n"
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(result)
    result += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    result += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    return result + f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


def serve(root):
    from review import create_app
    from review.documents import create_document, import_version
    from review.users import create_user
    import socket
    app = create_app({"DATABASE": str(root / "test.sqlite3"), "STORAGE_ROOT": str(root),
                      "TESTING": True, "SECRET_KEY": "browser-sanity-only"})
    doc = create_document(app.config["DATABASE"], "Browser sanity")
    versions = [import_version(app.config["DATABASE"], app.extensions["blob_store"], doc,
                              io.BytesIO(pdf_bytes(str(index))), f"draft{index}.pdf").version_id for index in [3, 4]]
    users = [create_user(app.config["DATABASE"], name) for name in ["ReviewerAlpha", "ReviewerBeta"]]
    # Issue signed fixture sessions offline; no login bypass route is exposed.
    from tests.auth_helpers import authenticate
    cookies = []
    for user in users:
        client = app.test_client()
        authenticate(client, user["user_id"])
        cookies.append(client.get_cookie(app.config["SESSION_COOKIE_NAME"]).value)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    (root / "fixture.json").write_text(json.dumps({"document_id": doc, "versions": versions, "users": users, "cookies": cookies, "port": port}))
    app.extensions["socketio"].run(app, host="127.0.0.1", port=port, allow_unsafe_werkzeug=True)


class DevTools:
    def __init__(self, url):
        from simple_websocket import Client
        self.ws = Client.connect(url)
        self.counter = 0
        self.exceptions = []

    def call(self, method, params=None, session=None):
        self.counter += 1
        message = {"id": self.counter, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        self.ws.send(json.dumps(message))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            raw = self.ws.receive(timeout=1)
            if raw is None:
                continue
            reply = json.loads(raw)
            if reply.get("method") == "Runtime.exceptionThrown":
                self.exceptions.append(reply)
            if reply.get("id") == self.counter:
                if "error" in reply:
                    raise RuntimeError(reply["error"])
                return reply.get("result", {})
        raise TimeoutError(method)

    def evaluate(self, session, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True,
                                                "awaitPromise": True, "userGesture": True}, session)
        if "exceptionDetails" in result:
            raise AssertionError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def wait(self, session, expression, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.evaluate(session, expression):
                return
            time.sleep(0.1)
        raise AssertionError(f"Browser condition timed out: {expression}; state=" + str(self.evaluate(session, "document.body.innerText")))


def verify_websocket_transport(base, fixture):
    """Exercise authenticated Socket.IO over actual WebSocket-only transport."""
    from simple_websocket import Client
    from urllib.parse import urlsplit
    endpoint = base.replace("http://", "ws://") + "/socket.io/?EIO=4&transport=websocket"
    for authenticated in (False, True):
        # simple-websocket's client sends Host without the non-default port.
        # Match that actual request origin; browser requests use the full origin.
        headers = {"Origin": "http://" + urlsplit(base).hostname}
        if authenticated:
            headers["Cookie"] = "pdf_review_session=" + fixture["cookies"][0]
        ws = Client.connect(endpoint, headers=headers)
        try:
            assert ws.receive(timeout=5).startswith("0"), "Engine.IO handshake missing"
            ws.send("40")
            packet = ws.receive(timeout=5)
            if not authenticated:
                assert packet.startswith("44"), "Anonymous WebSocket was not rejected"
                continue
            assert packet.startswith("40"), "Authenticated Socket.IO connect failed"
            ws.send('421' + json.dumps(["review.join", {"version_id": fixture["versions"][0]}]))
            for _ in range(5):
                packet = ws.receive(timeout=5)
                if packet.startswith("431"):
                    assert json.loads(packet[3:])[0]["ok"]
                    break
            else:
                raise AssertionError("Authenticated WebSocket room join did not acknowledge")
            ws.send("41")
        finally:
            ws.close()
    print("PASS WebSocket-only transport, anonymous rejection and authenticated ACL room join")


def run():
    chrome = next((path for path in [Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
                                     Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe"] if path.exists()), None)
    if chrome is None:
        raise RuntimeError("Chrome or Edge is required for this optional check.")
    with tempfile.TemporaryDirectory(prefix="pdf-review-browser-") as directory:
        root = Path(directory)
        server = browser = cdp = None
        with (root / "server.log").open("w") as log:
            try:
                server = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--server", str(root)],
                                          stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
                deadline = time.monotonic() + 15
                while not (root / "fixture.json").exists():
                    if time.monotonic() > deadline: raise TimeoutError("Fixture server startup")
                    time.sleep(0.1)
                fixture = json.loads((root / "fixture.json").read_text())
                base = f"http://127.0.0.1:{fixture['port']}"
                profile = root / "chrome"
                browser = subprocess.Popen([str(chrome), "--headless=new", "--remote-debugging-port=0",
                                            f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
                                            "--disable-background-networking", "--disable-extensions", "about:blank"],
                                           stdout=subprocess.DEVNULL, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
                deadline = time.monotonic() + 20
                while not (profile / "DevToolsActivePort").exists():
                    if time.monotonic() > deadline: raise TimeoutError("Chrome startup")
                    time.sleep(0.1)
                port, endpoint = (profile / "DevToolsActivePort").read_text().splitlines()[:2]
                cdp = DevTools(f"ws://127.0.0.1:{port}{endpoint}")
                sessions = []
                for index in range(2):
                    context = cdp.call("Target.createBrowserContext")["browserContextId"]
                    target = cdp.call("Target.createTarget", {"url": "about:blank",
                                                            "browserContextId": context})["targetId"]
                    session = cdp.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
                    sessions.append(session)
                    cdp.call("Runtime.enable", session=session)
                    cdp.call("Network.enable", session=session)
                    cdp.call("Network.setCookie", {"name": "pdf_review_session", "value": fixture["cookies"][index], "url": base, "httpOnly": True, "sameSite": "Lax"}, session)
                    cdp.call("Page.navigate", {"url": base + f"/versions/{fixture['versions'][0]}/view"}, session)
                    cdp.wait(session, "document.querySelector('#realtime-status')?.textContent === 'Live'")
                a, b = sessions
                verify_websocket_transport(base, fixture)
                for session in sessions:
                    cdp.wait(session, "document.querySelector('#review-presence').textContent.includes('ReviewerAlpha') && document.querySelector('#review-presence').textContent.includes('ReviewerBeta')")
                cdp.evaluate(b, "document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.currentPageNumber = 2")
                cdp.wait(a, "document.querySelector('#review-presence').textContent.includes('p. 2')")
                print("PASS live status, independent reviewer sessions, presence and page changes", flush=True)
                cdp.evaluate(a, """(() => {
                  const w=document.querySelector('iframe').contentWindow;
                  const text=w.document.querySelector('.textLayer span').firstChild;
                  const range=w.document.createRange(); range.selectNodeContents(text);
                  w.getSelection().removeAllRanges(); w.getSelection().addRange(range);
                  document.querySelector('#comment-selection-button').disabled=false;
                  document.querySelector('#comment-selection-button').click();
                  document.querySelector('#selection-comment-body').value='Browser root';
                  document.querySelector('#selection-comment-form').requestSubmit();
                })()""")
                cdp.wait(b, "document.querySelector('.thread-comment-body')?.textContent === 'Browser root'")
                cdp.wait(b, "document.querySelector('iframe').contentDocument.querySelector('.pdf-review-thread-highlight') !== null")
                cdp.evaluate(b, "document.querySelector('.thread-reply-form textarea').value='Browser reply'; document.querySelector('.thread-reply-form').requestSubmit()")
                cdp.wait(a, "document.querySelector('#thread-list').textContent.includes('Browser reply')")
                print("PASS selection creation, remote highlight and reply synchronization", flush=True)
                assert cdp.evaluate(b, "[...document.querySelectorAll('.thread-comment:first-child .text-action')].every(button=>button.textContent!=='Edit')")
                assert cdp.evaluate(a, "[...document.querySelectorAll('.thread-comment:nth-child(2) .text-action')].every(button=>button.textContent!=='Edit')")
                print("PASS author-only edit controls", flush=True)
                # Two sessions for the same author must still detect stale edits.
                cdp.call("Network.setCookie", {"name": "pdf_review_session", "value": fixture["cookies"][0], "url": base, "httpOnly": True, "sameSite": "Lax"}, b)
                cdp.call("Page.reload", session=b)
                cdp.wait(b, "[...document.querySelectorAll('.thread-comment:first-child .text-action')].some(button=>button.textContent==='Edit')")
                # Open both edit forms at the same revision, then retain B's draft during A's save.
                for session, text in [(a, "Browser edited"), (b, "Unsaved stale edit")]:
                    cdp.evaluate(session, f"document.querySelector('.thread-comment .text-action').click(); document.querySelector('.inline-edit-form textarea').value={json.dumps(text)}")
                cdp.evaluate(a, "document.querySelector('.inline-edit-form').requestSubmit()")
                cdp.wait(b, "document.querySelector('.thread-comment-body')?.textContent === 'Browser edited'")
                assert cdp.evaluate(b, "document.querySelector('.inline-edit-form textarea').value") == "Unsaved stale edit"
                cdp.evaluate(b, "document.querySelector('.inline-edit-form').requestSubmit()")
                cdp.wait(b, "document.querySelector('.edit-conflict')?.textContent.includes('changed in another browser')")
                assert cdp.evaluate(b, "document.querySelector('.inline-edit-form textarea').value") == "Unsaved stale edit"
                assert cdp.evaluate(a, "document.querySelector('.thread-comment-body').textContent") == "Browser edited"
                cdp.evaluate(b, "document.querySelector('.inline-edit-form .quiet-control').click()")
                print("PASS edit synchronization, 409 conflict and unsaved draft preservation", flush=True)
                cdp.call("Network.setCookie", {"name": "pdf_review_session", "value": fixture["cookies"][1], "url": base, "httpOnly": True, "sameSite": "Lax"}, b)
                cdp.call("Page.reload", session=b)
                cdp.wait(b, "document.querySelector('#realtime-status')?.textContent==='Live'")
                cdp.wait(a, "document.querySelector('#review-presence').textContent.includes('ReviewerBeta')")
                cdp.evaluate(b, "window.confirm=()=>true; document.querySelectorAll('.thread-comment')[1].querySelector('.danger').click()")
                cdp.wait(a, "document.querySelector('#thread-list').textContent.includes('This comment was deleted.')")
                for session in sessions:
                    cdp.evaluate(session, "document.querySelector('#thread-filter').value='all'; document.querySelector('#thread-filter').dispatchEvent(new Event('change'))")
                cdp.evaluate(a, "document.querySelector('.resolve-control').click()")
                cdp.wait(b, "document.querySelector('.thread-card').classList.contains('resolved')")
                cdp.wait(b, "document.querySelector('.thread-status-history').textContent.includes('Resolved by ReviewerAlpha')")
                cdp.wait(b, "document.querySelector('iframe').contentDocument.querySelector('.pdf-review-thread-highlight.is-resolved') !== null")
                cdp.evaluate(b, "document.querySelector('.resolve-control').click()")
                cdp.wait(a, "!document.querySelector('.thread-card').classList.contains('resolved')")
                cdp.wait(a, "document.querySelector('.thread-status-history').textContent.includes('Reopened by ReviewerBeta') && document.querySelector('.thread-status-history').textContent.includes('Resolved by ReviewerAlpha')")
                # Centered navigation is still handled by the existing overlay.
                cdp.evaluate(b, "document.querySelector('.thread-card').click()")
                cdp.wait(b, "document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.currentPageNumber === 1")
                centered = cdp.evaluate(b, """(() => {
                  const d=document.querySelector('iframe').contentDocument;
                  const h=d.querySelector('.pdf-review-thread-highlight').getBoundingClientRect();
                  const v=d.querySelector('#viewerContainer').getBoundingClientRect();
                  return Math.abs((h.top+h.bottom)/2-(v.top+v.bottom)/2)<60;
                })()""")
                assert centered, "Highlight should be vertically centered"
                print("PASS tombstone, resolve/reopen, remote resolved highlight and centered navigation", flush=True)
                cdp.evaluate(b, """(async () => {
                  const config=JSON.parse(document.querySelector('#anchor-config').textContent);
                  const canonical=await (await fetch(config.threadsUrl)).json();
                  window.sanityRectangle=canonical.threads[0].targets[0].anchor.segments[0].rectangles[0];
                })()""")
                for scale, rotation in [(0.5, 0), (1, 0), (1.5, 0), (2, 0), (1, 90), (1, 0)]:
                    cdp.evaluate(b, f"document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.currentScale={scale}; document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.pagesRotation={rotation}")
                    cdp.wait(b, """(() => {
                      const w=document.querySelector('iframe').contentWindow;
                      const page=w.PDFViewerApplication.pdfViewer.getPageView(0);
                      const highlights=page.div.querySelectorAll('.pdf-review-thread-highlight');
                      if(highlights.length!==1) return false;
                      const h=highlights[0], v=page.viewport;
                      const r=window.sanityRectangle;
                      const [x1,y1]=v.convertToViewportPoint(r[0],r[1]);
                      const [x2,y2]=v.convertToViewportPoint(r[2],r[3]);
                      const sx=page.div.clientWidth/v.width, sy=page.div.clientHeight/v.height;
                      return Math.abs(parseFloat(h.style.left)-Math.min(x1,x2)*sx)<1 &&
                        Math.abs(parseFloat(h.style.top)-Math.min(y1,y2)*sy)<1 &&
                        Math.abs(parseFloat(h.style.width)-Math.abs(x2-x1)*sx)<1 &&
                        Math.abs(parseFloat(h.style.height)-Math.abs(y2-y1)*sy)<1;
                    })()""")
                print("PASS highlight geometry at 50/100/150/200 percent and 90-degree rotation", flush=True)
                # Block only the socket transport; HTTP review actions remain available.
                cdp.call("Network.setBlockedURLs", {"urls": ["*socket.io/*"]}, b)
                cdp.evaluate(b, "window.dispatchEvent(new PageTransitionEvent('pagehide')); window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}))")
                cdp.wait(b, "document.querySelector('#realtime-status').textContent !== 'Live'")
                cdp.evaluate(b, "document.querySelector('.thread-reply-form textarea').value='HTTP while offline'; document.querySelector('.thread-reply-form').requestSubmit()")
                cdp.wait(b, "document.querySelector('#thread-list').textContent.includes('HTTP while offline')")
                cdp.evaluate(a, "document.querySelector('.thread-reply-form textarea').value='Missed while disconnected'; document.querySelector('.thread-reply-form').requestSubmit()")
                cdp.wait(a, "document.querySelector('#thread-list').textContent.includes('Missed while disconnected')")
                cdp.call("Network.setBlockedURLs", {"urls": []}, b)
                cdp.wait(b, "document.querySelector('#realtime-status').textContent === 'Live'")
                cdp.wait(b, "document.querySelector('#thread-list').textContent.includes('Missed while disconnected')")
                print("PASS HTTP while realtime offline and reconnect canonical refetch", flush=True)
                # Switch B to the other exact version and verify named membership moves.
                cdp.call("Page.navigate", {"url": base + f"/versions/{fixture['versions'][1]}/view"}, b)
                cdp.wait(b, "document.querySelector('#realtime-status')?.textContent === 'Live'")
                cdp.wait(a, "!document.querySelector('#review-presence').textContent.includes('ReviewerBeta')")
                cdp.evaluate(a, "document.querySelector('.thread-reply-form textarea').value='Version isolated'; document.querySelector('.thread-reply-form').requestSubmit()")
                cdp.wait(a, "document.querySelector('#thread-list').textContent.includes('Version isolated')")
                time.sleep(0.5)
                assert cdp.evaluate(b, "document.querySelectorAll('.thread-card').length") == 0
                print("PASS version isolation and old-room presence cleanup", flush=True)
                # Exercise the serial refresh coordinator with controlled pending promises.
                result = cdp.evaluate(a, """(async () => {
                  const {RefreshCoordinator}=await import('/static/review/realtime.js');
                  let calls=0, applied=[], resolve;
                  const r=new RefreshCoordinator(()=>{calls++; return new Promise(done=>resolve=done)}, x=>applied.push(x), ()=>{});
                  const pending=r.request(); r.request(); r.request();
                  if(calls!==1) throw Error('overlapping refresh');
                  r.invalidate(); resolve('stale'); await new Promise(done=>setTimeout(done,0));
                  if(calls!==2 || applied.length) throw Error('stale read applied');
                  resolve('latest'); await pending;
                  return calls===2 && applied.join()==='latest';
                })()""")
                assert result
                migration_checks(cdp, a, b, fixture, base)
                assert not cdp.exceptions, cdp.exceptions
                print("PASS refresh coalescing, stale read suppression; no uncaught browser exceptions", flush=True)
            finally:
                if cdp:
                    try: cdp.call("Browser.close")
                    except Exception: pass
                    cdp.ws.close()
                if browser:
                    try: browser.wait(timeout=10)
                    except subprocess.TimeoutExpired: browser.terminate(); browser.wait(timeout=10)
                if server:
                    server.terminate()
                    server.wait(timeout=10)


def migration_checks(cdp, a, b, fixture, base):
    """Exercise Slice 5 through actual controls, keeping A on the source version."""
    root_thread = cdp.evaluate(a, "document.querySelector('.thread-card').dataset.threadId")
    select_text = """(() => {
      const w=document.querySelector('iframe').contentWindow;
      const text=w.document.querySelector('.page[data-page-number="PAGE"] .textLayer span').firstChild;
      const range=w.document.createRange(); range.selectNodeContents(text);
      w.getSelection().removeAllRanges(); w.getSelection().addRange(range);
    })()"""
    cdp.evaluate(a, select_text.replace("PAGE", "1"))
    cdp.wait(a, "!document.querySelector('#comment-selection-button').disabled")
    cdp.evaluate(a, "document.querySelector('#comment-selection-button').click(); document.querySelector('#selection-comment-body').value='Skip this discussion'; document.querySelector('#selection-comment-form').requestSubmit()")
    cdp.wait(a, "document.querySelectorAll('.thread-card').length===2")
    cdp.call("Page.navigate", {"url": base + f"/documents/{fixture['document_id']}"}, b)
    cdp.wait(b, "[...document.querySelectorAll('a')].some(a=>a.textContent.includes('Carry feedback forward'))")
    cdp.evaluate(b, "[...document.querySelectorAll('a')].find(a=>a.textContent.includes('Carry feedback forward')).click()")
    cdp.wait(b, "document.querySelector('#migration-start-form')?.dataset.ready==='true'")
    cdp.evaluate(b, f"document.querySelector('#migration-source').value={json.dumps(fixture['versions'][0])}; document.querySelector('#migration-target').value={json.dumps(fixture['versions'][1])}; document.querySelector('#migration-start-form').requestSubmit()")
    cdp.wait(b, "document.querySelectorAll('.migration-item').length===2")
    migration_url = cdp.evaluate(b, "location.href")
    migration_id = migration_url.split("migration=")[1]
    cdp.evaluate(b, f"document.querySelector('.migration-item[data-thread-id=\"{root_thread}\"]').click()")
    cdp.wait(b, "document.querySelector('#migration-preview').textContent.includes('Browser edited')")
    cdp.evaluate(b, select_text.replace("PAGE", "1"))
    cdp.wait(b, "!document.querySelector('#migration-carry').disabled")
    cdp.evaluate(b, "document.querySelector('#migration-carry').click()")
    cdp.wait(b, "document.querySelector('#migration-counts').textContent.includes('1 carried')")
    cdp.wait(b, f"document.querySelector('.thread-card[data-thread-id=\"{root_thread}\"]')!==null")
    old_anchor = cdp.evaluate(b, "document.querySelector('iframe').contentDocument.querySelector('.pdf-review-thread-highlight').dataset.anchorId")
    cdp.evaluate(b, "document.querySelector('.thread-reply-form textarea').value='Reply after carry'; document.querySelector('.thread-reply-form').requestSubmit()")
    cdp.wait(a, "document.querySelector('#thread-list').textContent.includes('Reply after carry')")
    cdp.evaluate(b, "document.querySelector('#thread-filter').value='all'; document.querySelector('#thread-filter').dispatchEvent(new Event('change'))")
    cdp.evaluate(a, f"document.querySelector('.thread-card[data-thread-id=\"{root_thread}\"] .resolve-control').click()")
    cdp.wait(b, f"document.querySelector('.thread-card[data-thread-id=\"{root_thread}\"]').classList.contains('resolved')")
    cdp.evaluate(b, f"document.querySelector('.thread-card[data-thread-id=\"{root_thread}\"] .resolve-control').click()")
    cdp.wait(a, f"!document.querySelector('.thread-card[data-thread-id=\"{root_thread}\"]').classList.contains('resolved')")
    print("PASS migration UI creation, manual carry, shared thread/reply and cross-version resolution", flush=True)
    cdp.evaluate(b, "document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.currentPageNumber=2")
    cdp.wait(b, "document.querySelector('iframe').contentDocument.querySelector('.page[data-page-number=\"2\"] .textLayer span')!==null")
    cdp.evaluate(b, select_text.replace("PAGE", "2"))
    cdp.wait(b, "!document.querySelector('#migration-carry').disabled")
    cdp.evaluate(b, "document.querySelector('#migration-carry').click()")
    cdp.wait(b, f"!document.querySelector('iframe').contentDocument.querySelector('.pdf-review-anchor-highlight[data-anchor-id=\"{old_anchor}\"]')")
    history = cdp.evaluate(b, f"(async()=> (await (await fetch('/api/threads/{root_thread}/targets')).json()).targets)()")
    assert len(history) == 3 and not next(target for target in history if target["anchor"]["anchor_id"] == old_anchor)["is_effective"]
    cdp.call("Page.navigate", {"url": base + f"/versions/{fixture['versions'][1]}/view"}, b)
    cdp.wait(b, f"document.querySelector('.thread-card[data-thread-id=\"{root_thread}\"]')!==null")
    cdp.evaluate(b, "document.querySelector('.thread-card').click()")
    cdp.wait(b, "document.querySelector('iframe').contentWindow.PDFViewerApplication.pdfViewer.currentPageNumber===2")
    cdp.wait(b, "document.querySelector('iframe').contentDocument.querySelectorAll('.pdf-review-thread-highlight').length===1")
    assert not cdp.evaluate(b, f"document.querySelector('iframe').contentDocument.querySelector('.pdf-review-anchor-highlight[data-anchor-id=\"{old_anchor}\"]')!==null")
    cdp.call("Page.navigate", {"url": migration_url}, b)
    cdp.wait(b, "document.querySelectorAll('.migration-item').length===2")
    cdp.evaluate(b, f"[...document.querySelectorAll('.migration-item')].find(button=>button.dataset.threadId!=={json.dumps(root_thread)}).click(); window.prompt=()=> 'Not relevant to this draft'; document.querySelector('#migration-skip').click()")
    cdp.wait(b, "document.querySelector('#migration-counts').textContent.includes('1 skipped')")
    cdp.wait(b, "!document.querySelector('#migration-complete').disabled")
    cdp.evaluate(b, "document.querySelector('#migration-complete').click()")
    cdp.wait(b, "document.querySelector('#migration-status').textContent.toLowerCase().includes('completed')")
    run = cdp.evaluate(b, f"(async()=> (await (await fetch('/api/migrations/{migration_id}')).json()).migration)()")
    assert run["status"] == "completed" and run["counts"] == {"pending": 0, "carried": 1, "skipped": 1}
    assert next(item for item in run["items"] if item["state"] == "skipped")["thread"]["status"] == "open"
    cdp.call("Page.navigate", {"url": base + f"/documents/{fixture['document_id']}/migrations"}, b)
    cdp.wait(b, "document.querySelector('.migration-run')?.textContent.includes('completed')")
    print("PASS re-anchor replacement after normal reload, historical preservation, skip, completion and run history", flush=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--server":
        serve(Path(sys.argv[2]))
    else:
        run()
