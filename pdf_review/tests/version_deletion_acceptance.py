"""Version deletion UI and live viewer retirement, synthetic data only."""
from tests.beta_c2_acceptance import navigate, request
from tests.viewer_acceptance import screenshot


def run_version_delete(cdp,a,b,fixture,base):
    ev=lambda script:cdp.evaluate(a,script)
    wait=lambda script:cdp.wait(a,script)
    doc=fixture['document_id'];version,other=fixture['versions']
    # The second viewer remains an ARC reviewer, never a deletion actor.
    result=ev(f"""(async()=>{{const r=await fetch('/documents/{doc}/access',{{method:'POST',body:new URLSearchParams({{csrf_token:document.querySelector('meta[name=csrf-token]').content,user_id:'{fixture['users'][1]['user_id']}',role:'reviewer',action:'grant'}})}});return r.status;}})()""")
    assert result==303 or result==200,result
    navigate(cdp,a,base+f'/documents/{doc}')
    wait("document.querySelectorAll('.version-actions .danger').length===2")
    ev(f"document.querySelector('a[href=\"/versions/{version}/delete\"]').click()")
    wait("document.querySelector('.version-delete-confirmation')!==null")
    assert ev("document.querySelector('h1').textContent==='Delete this version?'&&document.querySelector('.version-delete-confirmation').textContent.includes('draft3.pdf')")
    assert request(cdp,a,f'/api/versions/{version}/reading')['status']==200
    screenshot(cdp,a,'version-delete-confirmation')
    ev("document.querySelector('.version-delete-confirmation .dialog-actions a').click()")
    wait("document.querySelectorAll('.version-card').length===2")
    ev(f"document.querySelector('a[href=\"/versions/{version}/delete\"]').click()")
    wait("document.querySelector('.version-delete-confirmation button')!==null")
    ev("document.querySelector('.version-delete-confirmation button').click()")
    wait(f"location.pathname==='/documents/{doc}'&&document.querySelectorAll('.version-card').length===1")
    cdp.wait(b,f"location.pathname==='/documents/{doc}'&&document.querySelectorAll('.version-card').length===1")
    assert cdp.evaluate(b,"document.querySelectorAll('.version-actions .danger').length===0")
    assert request(cdp,a,f'/versions/{version}/pdf')['status']==404
    assert ev(f"!!document.querySelector('a[href=\"/versions/{other}/view\"]')")
    screenshot(cdp,a,'version-delete-document')
    ev(f"document.querySelector('a[href=\"/versions/{other}/delete\"]').click()")
    wait("document.querySelector('.version-delete-confirmation button')!==null")
    ev("document.querySelector('.version-delete-confirmation button').click()")
    wait("document.querySelector('.empty-state')!==null&&document.querySelectorAll('.version-card').length===0")
    assert ev("!!document.querySelector('input[type=file]')")
    print('PASS owner confirmation/cancel, exact-version deletion, reviewer controls, live viewer redirect, old PDF 404, last-version empty state and upload availability',flush=True)
