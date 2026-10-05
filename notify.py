"""Emails from Alice: today, a decision held for approval goes to its owner (the category's owner, else the default approver).

Sent through Microsoft Graph as the mailbox in ALICE_MAIL_FROM, with the app's managed identity (no password or secret
anywhere): azure-setup.ps1 -Step mail grants that identity Mail.Send and sets ALICE_MAIL_FROM and ALICE_PUBLIC_URL. Not set
up (the PC, the tests, or before -Step mail): nothing is sent, the held decision waits on Actions as before, and the activity
log says why no email went. The demo Alice never sends email. Every email is checked for secrets and protective markings
first; if it fails, it goes without the decision text ("open Alice to read it"). Each send, or failure, is logged."""
import json
import os
import re
import time
import urllib.parse
import urllib.request

import substrate_store as store

EMAIL = re.compile(r"[A-Za-z0-9._%+'\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_token = {'value': '', 'until': 0.0}


def configured():
    return bool(EMAIL.fullmatch(os.environ.get('ALICE_MAIL_FROM', '').strip()) and os.environ.get('IDENTITY_ENDPOINT')
                and os.environ.get('IDENTITY_HEADER'))


def _http(url, data=None, headers=None, timeout=15):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method='POST' if data is not None else 'GET')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode('utf-8') or '{}'
        return r.status, json.loads(body) if body.strip().startswith('{') else {}


HTTP = _http                 # replaced in tests


def _graph_token():
    now = time.time()
    if _token['value'] and now < _token['until'] - 60: return _token['value']
    q = {'resource': 'https://graph.microsoft.com', 'api-version': '2019-08-01'}
    cid = os.environ.get('ALICE_IDENTITY_CLIENT_ID', '')
    if cid: q['client_id'] = cid
    _, d = HTTP(os.environ['IDENTITY_ENDPOINT'] + '?' + urllib.parse.urlencode(q), None, {'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']})
    _token['value'] = d['access_token']; _token['until'] = float(d.get('expires_on') or now + 3000)
    return _token['value']


def send(to, subject, text):
    """One plain-text email. Returns (sent: bool, why: str)."""
    import demo_instance
    if demo_instance.ON: return False, 'the demo Alice never sends email'
    to = (to or '').strip()
    if not EMAIL.fullmatch(to): return False, 'no owner email address is set'
    if not configured(): return False, 'email is not set up (azure-setup.ps1 -Step mail)'
    sender = os.environ['ALICE_MAIL_FROM'].strip()
    body = {'message': {'subject': subject[:200], 'body': {'contentType': 'Text', 'content': text[:20000]},
                        'toRecipients': [{'emailAddress': {'address': to}}]}, 'saveToSentItems': True}
    try:
        status, _ = HTTP(f'https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(sender)}/sendMail', json.dumps(body).encode('utf-8'),
                         {'Authorization': 'Bearer ' + _graph_token(), 'Content-Type': 'application/json'})
    except Exception as e:
        return False, f'Microsoft Graph refused it ({type(e).__name__}{": " + str(getattr(e, "code", "")) if getattr(e, "code", "") else ""})'
    return (status in (200, 202)), ('' if status in (200, 202) else f'Microsoft Graph answered {status}')


def decision_held(rid, why, to):
    """Email the owner of a decision held by the decision policy. Logs the outcome either way."""
    import rules_engine, refs
    with store.db() as c:
        r = c.execute('SELECT r.title,r.content,r.source FROM records r WHERE r.id=?', (rid,)).fetchone()
    if not r: return False
    meta = (store.record_kinds([rid]).get(rid) or {}).get('decision') or {}
    ref = refs.of('record', [rid]).get(rid, '')
    who = meta.get('made_by') or store.owner_name()
    link = (os.environ.get('ALICE_PUBLIC_URL', '').rstrip('/') or '') + '/admin/actions'
    detail = (f"Decision: {meta.get('decision') or r['content']}\n" + (f"Why: {meta['rationale']}\n" if meta.get('rationale') else '')
              + (f"Options considered: {', '.join(meta['options'])}\n" if meta.get('options') else ''))
    try: rules_engine.check_outbound(detail + r['title'], 'decision email', packs=False)
    except rules_engine.RuleViolation:
        detail = 'The decision text is not included in this email (it failed Alice\'s security checks): open Alice to read it.\n'
    text = (f"A decision is waiting for your approval in Alice.\n\n{ref + ': ' if ref else ''}{r['title']}\n\n{detail}\n"
            f"Made by: {who}" + (f" (via {meta['via']})" if meta.get('via') else '') + f"\nWhy it needs you: {why}\n\n"
            f"Approve or reject it on the Actions page: {link}\n\nThis email was sent by Alice. Do not reply.")
    ok, reason = send(to, f'Decision waiting for your approval: {r["title"]}', text)
    with store.db() as c:
        if ok: store.audit(c, 'decision_owner_emailed', rid, 'approval_required', f'Emailed {to}: {why}'[:500])
        else: store.audit(c, 'decision_owner_not_emailed', rid, 'approval_required', f'Not emailed ({reason}): waiting on Actions'[:500])
    return ok
