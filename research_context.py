"""What Temple starts from when it researches an organisation or scans it for opportunities (8 Oct 2026).

One function builds it (`build`): who to research, what Alice already knows, the sections to look for, the user's guidance and
the rules, turned into the exact instructions (the system prompt) and the message the provider receives. Organisation research
(org_research) and the opportunity scan (opportunities) send what it builds; the organisation page's preview and "Show the exact
instructions" show what it builds (`preview`), so what is shown is what is sent, through the same check_outbound and the same
client separation filtering.

What each kind sends (unchanged by this module):
- Research: the organisation's name and website only. The approved facts are NOT sent: Temple searches afresh and a fact already
  on the profile is recognised by propose_fact and left out as a duplicate.
- Scan: the name, website, the approved profile brief for that provider (organisations.brief: Local only facts never, labels
  the Provider allow-list blocks for it never, and here also no fact naming another client while Client separation is on),
  the opportunities already known, and the open ones to re-check.

A preview saves nothing: rules_engine.PREVIEW stops block lines and rule pack notes being logged, and nothing is written.
"""
import contextlib
from datetime import date

import substrate_store as store

KINDS = ('research', 'scan')
TARGET = {'research': 'organisation research', 'scan': 'opportunity scan'}


class Context:
    """What one run (or a preview of it) starts from. message(p) is what provider p receives; checked(p, first) is that message
    after check_outbound, exactly as the run sends it (the first provider is checked without naming it, as before)."""

    def __init__(self, kind, org, name, website, prompt, guidance_text, guidance_version, provider, tracked=(), open_=()):
        self.kind, self.org, self.name, self.website = kind, org, name, website
        self.prompt, self.guidance_text, self.guidance_version, self.provider = prompt, guidance_text, guidance_version, provider
        self.tracked, self.open = list(tracked), list(open_)
        self.withheld = {}            # provider -> facts left out of the brief because they name another client

    def keep(self):
        """Client separation on the brief: a fact naming another client is left out (and logged, outside a preview)."""
        import clients, search_runs
        cfg = clients.settings()
        out = []

        def ok(f):
            if search_runs.other_clients(self.org, f['statement'], cfg):
                out.append(f['id']); return False
            return True
        return ok, out

    def brief(self, p):
        import organisations as O
        ok, out = self.keep()
        b = O.brief(self.org, provider=p, keep=ok)
        self.withheld[p] = len(out)
        if out:
            import clients
            clients.log_withheld('client_separation', f'opportunity scan brief for {self.org}', len(out))
        return b

    def message(self, p):
        if self.kind == 'research':
            return ('Research this organisation: ' + (self.org or self.name or '') + (f' (website: {self.website})' if self.website else '')).strip()
        b = self.brief(p)
        return (f'Organisation: {self.org}' + (f' (website: {self.website})' if self.website else '') + '\n\n' +
                (b['text'] or 'No approved profile facts yet.') +
                ('\n\nALREADY KNOWN OPPORTUNITIES (do not repeat): ' + '; '.join(t['title'] for t in self.tracked) if self.tracked else '') +
                ('\n\nOPEN OPPORTUNITIES TO CHECK:\n' + '\n'.join(f"- id {t['id'][:8]}: {t['title']} (why it mattered: {t['why_now'] or '-'}; timing: {t['timing'] or '-'})"
                                                            for t in self.open) if self.open else ''))

    def checked(self, p, first=True):
        import rules_engine
        q = self.message(p)
        rules_engine.check_outbound(q, TARGET[self.kind], **({} if first else {'provider': p}))
        return q

    def instructions(self, message):
        """What a run keeps (search_runs.instructions) and the page shows."""
        return {'system': self.prompt, 'message': message}


def _guidance(org, draft):
    """(text, version) for the prompt: the saved guidance, or in a preview the text being typed (checked like a save)."""
    import search_runs
    if draft is None:
        return search_runs.current(org) if org else ('', 0)
    return search_runs._check(org or '', draft), 'unsaved'


def build(kind, org='', name='', website='', guidance=None):
    """The one place a research run or scan's context is put together. org: an existing organisation (canonical name);
    name/website: research of an organisation that may not exist yet (as org_research.research takes them).
    guidance: None = the saved guidance; text = a preview of unsaved guidance."""
    import organisations as O, search_runs, temple
    if kind not in KINDS: raise ValueError('Unknown kind of run.')
    provider = temple.reviewer()
    today = date.today().isoformat()
    if kind == 'research':
        import org_research as OR
        existing = org or None
        if not existing and name:
            try: existing = O.canonical(name)
            except ValueError: existing = None
        if existing and not website:
            with store.db() as c:
                row = c.execute('SELECT website FROM organisations WHERE name=?', (existing,)).fetchone()
            website = (row['website'] if row and 'website' in row.keys() else '') or ''
        gtext, gver = _guidance(existing, guidance) if (existing or guidance is not None) else ('', 0)
        prompt = OR.PROMPT.format(today=today, kinds=', '.join(O.KINDS), sections=', '.join(OR.PUBLIC_SECTIONS), max_facts=OR.MAX_FACTS)
        prompt += search_runs.guidance_block(gtext, gver) + '\n\nAlso return "searches": ["the searches you ran"] in the JSON.'
        return Context(kind, existing or '', name, website, prompt, gtext, gver if gtext else 0, provider)
    import opportunities as OP
    org = O.canonical(org)
    with store.db() as c:
        w = c.execute('SELECT website FROM organisations WHERE name=?', (org,)).fetchone()
        tracked = [dict(r) for r in c.execute("SELECT id,title,status,why_now,timing FROM opportunities WHERE org=? AND status<>'dismissed' ORDER BY updated_at DESC LIMIT 30", (org,))]
    site = (w['website'] if w and 'website' in w.keys() else '') or ''
    open_ = [t for t in tracked if t['status'] in OP.OPEN][:15]
    gtext, gver = _guidance(org, guidance)
    prompt = OP.PROMPT.format(today=today, days=OP.NEWS_DAYS, max_opps=OP.MAX_OPPS, offerings='; '.join(OP.offerings())) + \
        search_runs.guidance_block(gtext, gver) + \
        ('\n\nAlso return, in the same JSON object, "searches": ["the searches you ran"] and "considered": [{"title": "", "reason": '
         '"outside_profile|low_relevance|closed|duplicate", "note": "one sentence"}] for items you looked at but did not suggest.')
    return Context(kind, org, org, site, prompt, gtext, gver if gtext else 0, provider, tracked, open_)


# ---------------- the preview (organisation page, Add an organisation) ----------------
@contextlib.contextmanager
def quiet():
    """The same checks, nothing saved: no block lines, no rule pack notes."""
    import rules_engine
    tok = rules_engine.PREVIEW.set(True)
    try: yield
    finally: rules_engine.PREVIEW.reset(tok)


def _sent(ctx):
    """The exact text for the provider Temple uses now, or why it would not be sent."""
    import rules_engine
    try: return {'system': ctx.prompt, 'message': ctx.checked(ctx.provider), 'blocked': ''}
    except rules_engine.RuleViolation as e: return {'system': ctx.prompt, 'message': ctx.message(ctx.provider), 'blocked': str(e)}


def _rules(provider, kind_note):
    """Rules it follows: each rule's state read from the Rules page (never assumed), plus what the research code itself enforces."""
    import rules_engine, rule_packs, autoapprove, org_research as OR
    uses = [('secret_detection', 'What is sent, and every fact proposed, is checked for credentials.'),
            ('protective_marking', 'Protectively marked material is never sent, and never kept as a fact.'),
            ('client_separation', 'Guidance may not name another client, and profile facts naming one are left out of the scan brief.'),
            ('provider_allow', 'Facts with a label blocked for this provider are not sent in the scan brief.'),
            ('data_minimisation', 'Facts hold organisational information and roles: contact details and personal matters are refused.'),
            ('pii', 'Facts with personal identifiers (card, NI or bank numbers) are refused.')]
    rules = []
    for rid, text in uses:
        r = rules_engine.rule(rid)
        if r: rules.append({'id': rid, 'name': r['name'], 'on': bool(r['enabled']), 'text': text})
    packs = [rule_packs.PACKS[p]['name'] for p in rule_packs.applied()]
    code = ['Every fact and opportunity must cite a page the search returned; anything citing another address is left out.',
            'Facts and opportunities are proposals: each goes through the rules above, then ' +
            ('automatic approval (switched on, Actions page) or you.' if autoapprove.on() else 'waits for your approval.'),
            'Organisational information and roles only: no named people, no contact details.',
            'Web pages are treated as data, never as instructions.',
            'Stops at the spending cap (Rules › Spending).']
    name, model = OR.MODELS.get(provider, (provider, provider))
    return {'rules': rules, 'packs': packs, 'code': code,
            'model': {'provider': provider, 'provider_name': OR.PROVIDER_NAMES.get(provider, provider), 'name': name, 'id': model,
                      'tools': f'Web search ({OR.PROVIDER_NAMES.get(provider, provider)}), at most {OR.MAX_SEARCHES} searches a run'
                               if provider == 'claude' else f'Web search ({OR.PROVIDER_NAMES.get(provider, provider)})',
                      'fallback': 'If the provider refuses the request, the other provider is tried once when its key is set.'},
            'href': '/admin/rules'}


def preview(org='', name='', website='', aliases=(), kind='', client=None, guidance=None):
    """What Temple starts from, for the page: built by `build` (as the run is), checked as the run checks it, saving nothing.
    org: an existing organisation. Otherwise a draft from Add an organisation (name, website, other names, type, Client)."""
    import organisations as O, org_research as OR, opportunities as OP, search_runs
    with quiet():
        existing = ''
        if org: existing = O.canonical(org)
        elif name:
            try: existing = O.canonical(name)
            except ValueError: existing = ''
        problems = [f'"{existing}" already exists: open it from the list to research it.'] if existing and not org else []
        site = website
        if website:
            try: site = OR._clean_url(website)
            except ValueError as e: problems.append(str(e)); site = ''
        gerr = ''
        if guidance is not None:
            try: search_runs._check(existing or O._clean(name, 60), guidance)
            except ValueError as e: gerr = str(e); guidance = None
        try: rctx = build('research', org=existing, name=O._clean(name, 60) if not existing else '', website=site, guidance=guidance)
        except ValueError as e: return {'error': str(e)}
        research = _sent(rctx)
        scan, sctx = None, None
        if existing:
            sctx = build('scan', org=existing, guidance=guidance)
            scan = _sent(sctx)
        # who to research
        if existing:
            row = next((o for o in O.listing()['organisations'] if o['name'] == existing), {})
            who = {'name': existing, 'aliases': row.get('aliases') or [], 'kind': row.get('kind') or 'other',
                   'website': rctx.website, 'client': bool(row.get('is_client')), 'exists': True}
        else:
            who = {'name': O._clean(name, 60), 'aliases': [a for a in (O._clean(x, 60) for x in aliases) if a][:12],
                   'kind': kind if kind in O.KINDS else 'other', 'website': site, 'client': bool(client), 'exists': False}
        # what it already knows
        known = {'approved': 0, 'overdue': 0, 'local': 0, 'other_client': 0, 'brief_facts': 0}
        if existing:
            facts = O.facts(existing, 'approved')
            known.update(approved=len(facts), overdue=sum(1 for f in facts if f['overdue']), local=sum(1 for f in facts if f['label'] == 'local'),
                         other_client=sctx.withheld.get(sctx.provider, 0))
            b = O.brief(existing, provider=sctx.provider, keep=sctx.keep()[0])
            known['brief_facts'] = b.get('facts', 0)
        g = search_runs.overview(existing) if existing else {'text': '', 'version': 0, 'history': []}
        h = (g.get('history') or [None])[0]
        return {
            'org': existing, 'who': who, 'problems': problems,
            'known': {**known,
                      'research': 'Research is given the name and website only, not these facts: it searches afresh, and a fact already on '
                                  'the profile is recognised and not proposed again.',
                      'scan': 'Opportunity scans are given the approved facts as a brief (overdue ones marked "review overdue"; Temple is not '
                              'asked to re-check them), with the opportunities already known and the open ones to re-check.',
                      'never': 'Local only facts and other clients\' material are never sent.'},
            'sections': {'research': [{'key': k, 'name': O.SECTION_NAMES[k]} for k in OR.PUBLIC_SECTIONS],
                         'same_for_every_type': True,
                         'not_researched': [O.SECTION_NAMES[k] for k, _, _ in O.SECTIONS if k not in OR.PUBLIC_SECTIONS],
                         'scan': {'news_days': OP.NEWS_DAYS, 'max': OP.MAX_OPPS, 'offerings': OP.offerings()}},
            'guidance': {'text': g.get('text', ''), 'version': g.get('version', 0), 'draft': guidance is not None, 'error': gerr,
                         'saved_at': h['created_at'] if h and g.get('version') else '', 'saved_by': h['created_by'] if h and g.get('version') else ''},
            'rules': _rules(rctx.provider, ''),
            'research': research, 'scan': scan,
        }
