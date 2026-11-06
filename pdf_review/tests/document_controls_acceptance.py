"""Document control layout, persistent main selection and owner labels in Chrome."""
import json

from tests.viewer_acceptance import viewport, screenshot, click


def run_document_controls(cdp, a, b, fixture, base):
    doc = fixture['document_id']
    path = '/documents/' + doc
    cdp.call('Page.navigate', {'url': base + path}, a)
    cdp.wait(a, "document.querySelectorAll('.main-version-toggle').length===2")
    for width, height in ((1440, 900), (768, 1024), (390, 844)):
        viewport(cdp, a, width, height)
        assert cdp.evaluate(a, "document.documentElement.scrollWidth<=innerWidth+1")
        assert cdp.evaluate(a, "document.querySelector('.document-controls > a:not([data-share-document])')?.textContent==='Manage access' && !document.querySelector('.document-actions a[href$=\"/access\"]')")
        assert cdp.evaluate(a, """[...document.querySelectorAll('.version-card')].every(card=>{
          const group=card.querySelector('.version-secondary-controls'), verify=group.querySelector('button').getBoundingClientRect(), main=group.querySelector('.main-version-toggle').getBoundingClientRect(), box=card.getBoundingClientRect();
          return verify.right<=main.left && Math.abs(verify.top-main.top)<2 && Math.abs(box.right-main.right-13)<2 && Math.abs(box.bottom-main.bottom-13)<2;
        })""")
        screenshot(cdp, a, 'document-controls-' + str(width))
        click(cdp, a, '.document-actions > summary')
        cdp.wait(a, "document.querySelector('.document-actions').open")
        click(cdp, a, '.delete-version-menu > summary')
        cdp.wait(a, "document.querySelector('.delete-version-menu').open")
        assert cdp.evaluate(a, "document.querySelectorAll('.delete-version-menu a').length===2 && document.querySelectorAll('.version-actions a[href$=\"/delete\"]').length===0")
        cdp.wait(a, """(()=>{const r=document.querySelector('.delete-version-menu > .toolbar-popover').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1;})()""")
        screenshot(cdp, a, 'document-delete-picker-' + str(width))
        cdp.evaluate(a, "document.querySelector('.document-actions').open=false")

    viewport(cdp, a, 1440, 900)
    selected = cdp.evaluate(a, "document.querySelector('.main-version-toggle[aria-pressed=false]').form.action")
    click(cdp, a, '.main-version-toggle[aria-pressed=false]')
    cdp.wait(a, "document.querySelector('.message')?.textContent.includes('Main version updated')")
    assert cdp.evaluate(a, "document.querySelectorAll('.main-version-toggle[aria-pressed=true]').length===1 && document.querySelector('.main-version-toggle[aria-pressed=true]').form.action===" + json.dumps(selected))
    cdp.call('Page.reload', {}, a)
    cdp.wait(a, "document.querySelector('.main-version-toggle[aria-pressed=true]')?.form.action===" + json.dumps(selected))
    cdp.call('Page.navigate', {'url': base + '/'}, a)
    cdp.wait(a, "document.querySelector('.document-owners')!==null")
    assert cdp.evaluate(a, "document.querySelector(" + json.dumps('a.document-card[href="/documents/' + doc + '"] .document-owners') + ").textContent.includes('ReviewerAlpha')")
    screenshot(cdp, a, 'document-dashboard-owners')
    print('PASS document controls/owner labels, bottom-right integrity/main buttons, bounded version picker, and persistent single main version at desktop/tablet/mobile widths', flush=True)
