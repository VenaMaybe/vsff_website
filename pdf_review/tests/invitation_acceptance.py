"""Focused browser acceptance using the existing synthetic fixture and offline provider."""

import json

from tests.viewer_acceptance import viewport, screenshot


def run_invitations(cdp, a, b, fixture, base):
    owner = fixture['users'][0]['user_id']
    reader = fixture['users'][1]['user_id']

    def navigate(session, path, condition):
        cdp.call('Page.navigate', {'url': base + path}, session)
        cdp.wait(session, condition)

    def cookie(session, value):
        cdp.call('Network.setCookie', {'name': 'pdf_review_session', 'value': value, 'url': base, 'httpOnly': True, 'sameSite': 'Lax'}, session)

    cookie(a, fixture['admin_cookie'])
    navigate(a, '/admin', "document.body.innerText.includes('Trusted Users')")
    status = cdp.evaluate(a, f"""(async()=>{{const r=await fetch('/admin/trusted-users',{{method:'POST',headers:{{'X-CSRF-Token':document.querySelector('meta[name=csrf-token]').content}},body:new URLSearchParams({{user_id:{json.dumps(owner)},action:'grant'}})}});return r.status;}})()""")
    assert status == 200
    cookie(a, fixture['cookies'][0])
    navigate(a, '/members', "document.querySelector('h1')?.textContent==='Beta members'")
    assert cdp.evaluate(a, "document.querySelectorAll('article.access-row').length===3 && document.body.innerText.includes('Trusted User') && document.body.innerText.includes('Site Admin') && document.body.innerText.includes('ReviewerBeta')")
    assert not cdp.evaluate(a, "document.body.innerText.includes('C1 shared fixture')")
    for width, height in ((1440, 900), (390, 844)):
        viewport(cdp, a, width, height)
        assert cdp.evaluate(a, 'document.documentElement.scrollWidth<=innerWidth+1')
        screenshot(cdp, a, f'invitations-members-{width}')

    viewport(cdp, a, 1440, 900)
    navigate(a, '/documents/' + fixture['document_id'] + '/access', "document.body.innerText.includes('Share by email')")
    cdp.evaluate(a, """(()=>{const f=document.querySelector('form[action$="/invitations"]');f.elements.email.value='browser-newbeta@example.test';f.elements.role.value='reviewer';f.requestSubmit();})()""")
    cdp.wait(a, "document.getElementById('invitation-link')!==null")
    link = cdp.evaluate(a, "document.getElementById('invitation-link').value")
    assert '#token=' in link
    screenshot(cdp, a, 'invitations-created')

    # A forwarded link cannot grant the currently signed-in wrong account access.
    cdp.call('Page.navigate', {'url': link}, b)
    cdp.wait(b, "document.querySelector('#invitation-open button')?.disabled===false")
    assert cdp.evaluate(b, "location.hash==='' && document.querySelector('#invitation-open').elements.token.value.length===64")
    cdp.evaluate(b, "document.querySelector('#invitation-open').requestSubmit()")
    cdp.wait(b, "document.body.innerText.includes('Use your invited Google account')")
    screenshot(cdp, b, 'invitations-wrong-account')

    context = cdp.call('Target.createBrowserContext')['browserContextId']
    target = cdp.call('Target.createTarget', {'url': 'about:blank', 'browserContextId': context})['targetId']
    recipient = cdp.call('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
    cdp.call('Runtime.enable', session=recipient)
    cdp.call('Network.enable', session=recipient)
    cdp.call('Page.navigate', {'url': link}, recipient)
    cdp.wait(recipient, "document.querySelector('#invitation-open button')?.disabled===false")
    cdp.evaluate(recipient, "document.querySelector('#invitation-open').requestSubmit()")
    cdp.wait(recipient, f"location.pathname==='/documents/{fixture['document_id']}' && document.querySelector('h1')!==null")
    assert cdp.evaluate(recipient, "document.querySelector('a[href=\"/members\"]')===null")
    result = cdp.evaluate(recipient, f"(async()=> (await fetch('/versions/{fixture['versions'][0]}/pdf')).status)()")
    assert result == 200
    screenshot(cdp, recipient, 'invitations-accepted-document')

    # A share appears in an already-open dashboard, preserving a typed title draft.
    cookie(b, fixture['cookies'][1])
    navigate(b, '/', "document.querySelector('.document-grid')!==null")
    assert not cdp.evaluate(b, f"document.querySelector('a[href=\"/documents/{fixture['owned']}\"]')!==null")
    cdp.evaluate(b, "document.querySelector('input[name=title]').value='Keep my document draft'")
    navigate(a, '/documents/' + fixture['owned'] + '/access', "document.body.innerText.includes('Share by email')")
    cdp.evaluate(a, f"""(()=>{{const f=document.querySelector('form[action$="/invitations"]');f.elements.email.value={json.dumps(reader+'@example.test')};f.requestSubmit();}})()""")
    cdp.wait(a, "document.body.innerText.includes('Access has been granted')")
    cdp.evaluate(b, "window.dispatchEvent(new Event('focus'))")
    cdp.wait(b, f"document.querySelector('a[href=\"/documents/{fixture['owned']}\"]')!==null")
    assert cdp.evaluate(b, "document.querySelector('input[name=title]').value==='Keep my document draft'")

    cookie(a, fixture['admin_cookie'])
    navigate(a, '/admin/history', "document.querySelector('h1')?.textContent==='Access history'")
    assert cdp.evaluate(a, "document.querySelector('[data-action=\"invitation.accepted\"]')!==null && document.querySelector('[data-action=\"invitation.immediate_share\"]')!==null")
    viewport(cdp, a, 390, 844)
    assert cdp.evaluate(a, 'document.documentElement.scrollWidth<=innerWidth+1')
    screenshot(cdp, a, 'invitations-history-mobile')
    cdp.call('Target.disposeBrowserContext', {'browserContextId': context})
    print('PASS Trusted User administration, directory privacy/responsiveness, wrong-account rejection, invitation sign-in/direct document access, audit history, and dashboard refresh preserving drafts', flush=True)
