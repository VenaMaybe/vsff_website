"""Share dialog: responsive native modal, inline submission/retry and invitation copy."""
import json

from tests.viewer_acceptance import viewport, screenshot, click, key


def run_share_dialog(cdp, a, b, fixture, base):
    owner = fixture['users'][0]['user_id']
    cdp.call('Network.setCookie', {'name': 'pdf_review_session', 'value': fixture['admin_cookie'], 'url': base, 'httpOnly': True, 'sameSite': 'Lax'}, a)
    cdp.call('Page.navigate', {'url': base + '/admin'}, a)
    cdp.wait(a, "document.querySelector('meta[name=csrf-token]')!==null")
    result = cdp.evaluate(a, f"""(async()=> (await fetch('/admin/trusted-users',{{method:'POST',headers:{{'X-CSRF-Token':document.querySelector('meta[name=csrf-token]').content}},body:new URLSearchParams({{user_id:{json.dumps(owner)},action:'grant'}})}})).status)()""")
    assert result == 200
    cdp.call('Network.setCookie', {'name': 'pdf_review_session', 'value': fixture['cookies'][0], 'url': base, 'httpOnly': True, 'sameSite': 'Lax'}, a)
    path = '/documents/' + fixture['document_id']
    cdp.call('Page.navigate', {'url': base + path}, a)
    cdp.wait(a, "document.querySelector('[data-share-document]')!==null")
    for width, height in ((1440, 900), (390, 844)):
        viewport(cdp, a, width, height)
        click(cdp, a, '[data-share-document]')
        cdp.wait(a, "document.querySelectorAll('.share-dialog [data-share-form]').length===2")
        assert cdp.evaluate(a, "document.querySelector('dialog').open && document.querySelectorAll('dialog').length===1 && document.activeElement.closest('dialog')!==null")
        assert cdp.evaluate(a, """(()=>{const d=document.querySelector('.share-dialog'),r=d.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1&&d.scrollWidth<=d.clientWidth+1;})()""")
        screenshot(cdp, a, 'share-dialog-' + str(width))
        key(cdp, a, 'Escape', 27)
        cdp.wait(a, "document.querySelector('dialog')===null && document.activeElement.matches('[data-share-document]')")

    viewport(cdp, a, 1440, 900)
    click(cdp, a, '[data-share-document]')
    cdp.wait(a, "document.querySelector('[data-share-form=existing]')!==null")
    cdp.evaluate(a, f"""(()=>{{const f=document.querySelector('[data-share-form=existing]');f.elements.user_id.value={json.dumps(fixture['users'][1]['user_id'])};f.elements.role.value='viewer';f.requestSubmit();}})()""")
    cdp.wait(a, "document.querySelector('[data-share-result]')?.textContent.includes('Access granted')")
    assert cdp.evaluate(a, "location.pathname===" + json.dumps(path))

    # Preserve an email draft after a server/network failure and allow a clean retry.
    cdp.evaluate(a, """(()=>{const f=document.querySelector('[data-share-form=email]');f.elements.email.value='share-dialog-new@example.test';const original=window.fetch;window.fetch=()=>{window.fetch=original;return Promise.resolve(new Response(JSON.stringify({error:{message:'Temporary sharing failure'}}),{status:503,headers:{'Content-Type':'application/json'}}));};f.requestSubmit();})()""")
    cdp.wait(a, "document.querySelector('[data-share-error]')?.textContent==='Temporary sharing failure'")
    assert cdp.evaluate(a, "document.querySelector('[data-share-form=email]').elements.email.value==='share-dialog-new@example.test'")
    cdp.evaluate(a, "document.querySelector('[data-share-form=email]').requestSubmit()")
    cdp.wait(a, "document.querySelector('[data-share-result] input[readonly]')?.value.includes('#token=')")
    assert cdp.evaluate(a, "document.querySelector('.share-dialog').getAttribute('aria-busy')==='false' && document.querySelector('[data-share-error]').hidden")
    screenshot(cdp, a, 'share-dialog-invitation-ready')
    click(cdp, a, '.dialog-header button')
    cdp.wait(a, "document.querySelector('dialog')===null")
    cdp.call('Page.navigate', {'url': base + path}, b)
    cdp.wait(b, "document.querySelector('h1')!==null")
    assert not cdp.evaluate(b, "document.querySelector('[data-share-document]')!==null")
    print('PASS Share dialog desktop/mobile bounds, focus/Escape, inline existing-member grant, preserved email/error/retry, copyable new invitation and owner-only visibility', flush=True)
