"""Demo data for the Organisations and Opportunities pages, kept apart from your real data.

SQLite: a separate file, data/demo/substrate-demo.db. PostgreSQL: a separate schema, alice_demo.
The demo store is built from the live schema (tables only, no rows), then the rules and settings are copied (so the
same rules apply) and fictional organisations, facts, opportunities and news are added. Nothing in the demo store is
real, and nothing outside the two demo pages ever reads it: the switch happens per request (substrate_store.DATASET)
and only for /admin/api/organisations* and /admin/api/opportunities*. Research and opportunity scans are refused in
demo, because they would call real AI services.

If the live schema changes (a new column or table), the demo store is rebuilt and reseeded automatically.
"""
import hashlib
import json
import threading
import uuid
from datetime import date, datetime, timedelta, timezone

import substrate_store as store

_lock = threading.Lock()
COPY_TABLES = ('rules', 'settings')   # same rules and settings as live: no personal data in either


def _live_schema():
    with store.dataset('live'):
        with store.db() as c:
            if store.DATABASE_URL:
                rows = [(r[0], r[1], r[2], r[3]) for r in c.execute(
                    "SELECT table_name, column_name, data_type, column_default FROM information_schema.columns "
                    "WHERE table_schema=current_schema() ORDER BY table_name, ordinal_position")]
                schema = c.execute('SELECT current_schema()').fetchone()[0]
                return schema, rows, hashlib.sha256(json.dumps(rows).encode()).hexdigest()[:16]
            rows = [(r[0], r[1], r[2]) for r in c.execute(
                "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, name")]
            return 'main', rows, hashlib.sha256(json.dumps(rows).encode()).hexdigest()[:16]


def _demo_fingerprint():
    try:
        with store.dataset('demo'):
            with store.db() as c:
                row = c.execute("SELECT value FROM settings WHERE key='demo_schema'").fetchone()
        return row[0] if row else ''
    except Exception:
        return ''


def ensure():
    """Build (or rebuild) and seed the demo store if it is missing or out of date with the live schema."""
    schema, rows, fp = _live_schema()
    if _demo_fingerprint() == fp: return False
    with _lock:
        if _demo_fingerprint() == fp: return False
        _build(schema, rows)
        _copy_live()
        with store.dataset('demo'):
            _seed()
            with store.db() as c:
                c.execute('INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('demo_schema', fp))
    return True


def reset():
    """Throw the demo data away and start again from the fictional set."""
    with _lock:
        schema, rows, fp = _live_schema()
        _build(schema, rows)
        _copy_live()
        with store.dataset('demo'):
            _seed()
            with store.db() as c:
                c.execute('INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('demo_schema', fp))
    return {'reset': True}


def _build(schema, rows):
    if store.DATABASE_URL:
        with store.dataset('live'):
            with store.db() as c:
                c.execute(f'DROP SCHEMA IF EXISTS {store.DEMO_SCHEMA} CASCADE')
                c.execute(f'CREATE SCHEMA {store.DEMO_SCHEMA}')
                for t in sorted({r[0] for r in rows}):
                    c.execute(f'CREATE TABLE {store.DEMO_SCHEMA}."{t}" (LIKE "{schema}"."{t}" INCLUDING ALL)')
                # LIKE copies defaults that point at the live sequences: give the demo tables their own.
                for t, col in [tuple(r) for r in c.execute(
                        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema=? AND column_default LIKE ?",
                        (store.DEMO_SCHEMA, 'nextval(%'))]:
                    seq = f'{store.DEMO_SCHEMA}."{t}_{col}_seq"'
                    c.execute(f'CREATE SEQUENCE {seq} OWNED BY {store.DEMO_SCHEMA}."{t}"."{col}"')
                    c.execute(f"ALTER TABLE {store.DEMO_SCHEMA}.\"{t}\" ALTER COLUMN \"{col}\" SET DEFAULT nextval('{seq}')")
        return
    path = store.DEMO_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    for p in (path, path.with_name(path.name + '-journal'), path.with_name(path.name + '-wal')):
        try: p.unlink()
        except FileNotFoundError: pass
    with store.dataset('demo'):
        with store.db() as c:
            for kind, name, sql in rows:
                if kind == 'table': c.execute(sql)
            for kind, name, sql in rows:
                if kind == 'index': c.execute(sql)


def _copy_live():
    for t in COPY_TABLES:
        with store.dataset('live'):
            with store.db() as c:
                data = [tuple(r) for r in c.execute(f'SELECT * FROM {t}')]
                cols = [r['name'] for r in c.execute(f'PRAGMA table_info({t})')]
        if not data: continue
        q = f'INSERT INTO {t}({",".join(cols)}) VALUES ({",".join("?" * len(cols))})'
        with store.dataset('demo'):
            with store.db() as c:
                for row in data:
                    if t == 'settings' and row[0] in ('demo_schema', 'opportunity_offerings'): continue
                    c.execute(q, row)


# ---------------- the fictional set ----------------
ORGS = [
    # name, kind, client?, account manager, website, description
    ('Glenmorrow Council', 'council', True, 'Morven Hay', 'https://www.glenmorrow.example.gov.uk', 'Rural Highland local authority serving about 92,000 people.'),
    ('Strathaird City Council', 'council', True, 'Morven Hay', 'https://www.strathaird.example.gov.uk', 'City council for Strathaird, a university city of 210,000.'),
    ('Kinloch and Ardnish Council', 'council', True, 'Callum Reid', 'https://www.kinloch-ardnish.example.gov.uk', 'Coastal authority covering 23 islands and the Ardnish peninsula.'),
    ('Auchenvale Council', 'council', True, 'Callum Reid', 'https://www.auchenvale.example.gov.uk', 'Central belt authority with a large housing estate programme.'),
    ('Torran Islands Council', 'council', False, '', 'https://www.torran.example.gov.uk', 'Small island authority; shared services with neighbours.'),
    ('Dunmore Council', 'council', False, 'Isla Grant', 'https://www.dunmore.example.gov.uk', 'Mixed urban and rural authority in the south-west.'),
    ('North Carran Health Board', 'health', True, 'Isla Grant', 'https://www.northcarran.example.scot', 'Regional health board for 330,000 people across three councils.'),
    ('Lochside Integration Joint Board', 'health', False, 'Isla Grant', 'https://www.lochside-ijb.example.scot', 'Health and social care partnership for Lochside.'),
    ('Ardmore University', 'university', True, 'Ewan Mackay', 'https://www.ardmore.example.ac.uk', 'Research university with 18,000 students across two campuses.'),
    ('Benlaw University', 'university', False, 'Ewan Mackay', 'https://www.benlaw.example.ac.uk', 'Modern university focused on engineering and health sciences.'),
    ('Bellmont College', 'college', False, 'Ewan Mackay', 'https://www.bellmont.example.ac.uk', 'Further education college with six campuses.'),
    ('Caledon Regional Police', 'police', True, 'Callum Reid', 'https://www.caledon-police.example.police.uk', 'Fictional regional police service used for demonstrations.'),
    ('Scottish Lochs Water', 'public body', False, 'Morven Hay', 'https://www.lochswater.example.scot', 'Public water and waste water utility.'),
    ('Fernhill Housing Association', 'charity', False, '', 'https://www.fernhill.example.org.uk', 'Social landlord with 6,500 homes.'),
    ('Corrie Analytics Ltd', 'company', False, 'Isla Grant', 'https://www.corrie.example.co.uk', 'Data analytics firm; Microsoft partner.'),
    ('Kelpie Transport Partnership', 'public body', False, '', 'https://www.kelpie-transport.example.scot', 'Regional transport partnership for five councils.'),
]

FACT_SETS = {
    'council': [
        ('identity', '{n} is a {d}'),
        ('purpose', 'Its Council Plan 2024-29 prioritises tackling child poverty, net zero by 2040 and digital public services.'),
        ('structure', 'Organised into three directorates: People, Place, and Corporate Services, each led by an executive director.'),
        ('security', 'Holds Cyber Essentials Plus and reports against the Scottish Public Sector Cyber Resilience Framework.'),
        ('technology', 'Uses Microsoft 365 E3 across 4,200 users; a single-tenant consolidation is planned for 2027.'),
        ('commercial', 'Buys through Scottish Government and Scotland Excel frameworks; financial year runs April to March.'),
        ('vocabulary', 'Calls its transformation programme "One {short}".'),
    ],
    'health': [
        ('identity', '{n} is a {d}'),
        ('purpose', 'Its three-year plan focuses on reducing waiting times and moving services closer to home.'),
        ('security', 'Works to the NHS Scotland information security policy framework; DSPT-equivalent assessments annually.'),
        ('technology', 'Migrating 9,000 staff to the national Microsoft 365 tenant during 2026-27.'),
        ('commercial', 'Procures through NHS National Services Scotland frameworks.'),
    ],
    'university': [
        ('identity', '{n} is a {d}'),
        ('purpose', 'Strategy 2030 commits to a digital-first student experience and research computing growth.'),
        ('technology', 'Runs research workloads on Azure and student services on Microsoft 365 A5.'),
        ('security', 'ISO/IEC 27001 certified for central IT services.'),
        ('commercial', 'Buys through APUC frameworks; financial year runs August to July.'),
    ],
    'default': [
        ('identity', '{n} is a {d}'),
        ('purpose', 'Current corporate plan focuses on efficiency and better digital services.'),
        ('technology', 'Microsoft 365 user organisation; considering Copilot pilots in 2027.'),
    ],
}

OPPS = [
    ('Glenmorrow Council', 'Single-tenant consolidation', 'The council plans to consolidate four Microsoft 365 tenants into one by 2027.',
     'Committee approved the consolidation business case in September.', 'Tenant migration and consolidation', 'large', 0.78, 'pursuing',
     'Hold a discovery workshop with the digital lead.'),
    ('Strathaird City Council', 'Identity platform tender', 'Procurement for an identity and access management platform replacing on-premises directory services.',
     'Tender notice published, closing 28 November.', 'Identity and access (Entra ID)', 'medium', 0.82, 'suggested',
     'Download the tender pack and hold a bid/no-bid this week.'),
    ('North Carran Health Board', 'National tenant migration support', 'Support for moving 9,000 staff into the national Microsoft 365 tenant.',
     'Board paper sets a March 2027 deadline.', 'Tenant migration and consolidation', 'large', 0.66, 'tracking', 'Offer migration readiness assessment.'),
    ('Ardmore University', 'Research computing on Azure', 'Expansion of high-performance research computing to Azure.',
     'Strategy refresh names cloud research computing as a priority.', 'Azure cloud and infrastructure', 'medium', 0.55, 'suggested',
     'Introduce the Azure HPC specialist to the research IT lead.'),
    ('Caledon Regional Police', 'Cyber resilience review', 'Independent review of cyber resilience following sector incidents.',
     'Audit committee requested an action plan.', 'Cyber security and compliance', 'small', 0.48, 'suggested', 'Share the CAF assessment offer.'),
    ('Auchenvale Council', 'Copilot pilot', 'A 300-user Copilot pilot in housing and customer services.', 'Budget includes a digital innovation line for 2026-27.',
     'Copilot and AI adoption', 'small', 0.6, 'won', 'Agree success measures with the service leads.'),
    ('Kinloch and Ardnish Council', 'Ferry booking data platform', 'Analytics platform for ferry and transport bookings.',
     'Transport partnership funding announced.', 'Data and analytics (Fabric, Power Platform)', 'medium', 0.42, 'lost', 'Ask for feedback on the decision.'),
]

NEWS = [
    ('Strathaird City Council', 'Council publishes tender for identity and access platform', 'Closes 28 November.'),
    ('Glenmorrow Council', 'Committee backs single Microsoft 365 tenant by 2027', 'Business case approved.'),
    ('North Carran Health Board', 'Board sets March 2027 date for national tenant move', 'Board paper, September meeting.'),
    ('Ardmore University', 'University refreshes Strategy 2030 with research computing focus', 'Cloud named as a priority.'),
    ('Caledon Regional Police', 'Audit committee asks for cyber resilience action plan', 'Following incidents in the sector.'),
]


def _seed():
    today = date.today()
    with store.db() as c:
        for name, kind, is_client, mgr, site, desc in ORGS:
            if is_client:
                c.execute('INSERT INTO clients(name,aliases,created_at) VALUES (?,?,?) ON CONFLICT DO NOTHING', (name, '[]', store.now()))
            c.execute('INSERT INTO organisations(name,kind,description,created_at,website,account_manager) VALUES (?,?,?,?,?,?)',
                      (name, kind, desc, store.now(), site, mgr))
    n_fact = 0
    for i, (name, kind, is_client, mgr, site, desc) in enumerate(ORGS):
        facts = FACT_SETS.get(kind, FACT_SETS['default'])
        short = name.split()[0]
        for j, (section, text) in enumerate(facts):
            stmt = text.format(n=name, d=desc[0].lower() + desc[1:], short=short)
            by = 'Temple research' if (i + j) % 5 == 4 else 'you'
            status = 'proposed' if by != 'you' else 'approved'
            as_of = (today - timedelta(days=30 + 11 * j + 3 * i)).isoformat()
            review = (today + timedelta(days=200 - 37 * j)).isoformat() if (i * j) % 7 != 3 else (today - timedelta(days=12)).isoformat()
            with store.db() as c:
                c.execute('INSERT INTO org_facts(id,org,section,statement,source_system,source_ref,as_of,review_by,label,status,proposed_by,created_at,reviewed_at) '
                          'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (uuid.uuid4().hex, name, section, stmt, f'Public web: {site.split("//")[1]}',
                                                               f'{site}/{section}', as_of, review, 'general', status, by, store.now(),
                                                               store.now() if status == 'approved' else None))
            n_fact += 1
    now = datetime.now(timezone.utc)
    with store.db() as c:
        for k, (org, title, summary, why, offering, size, conf, status, step) in enumerate(OPPS):
            site = next(o[4] for o in ORGS if o[0] == org)
            c.execute('INSERT INTO opportunities(id,org,title,summary,why_now,offering,size,confidence,next_step,timing,evidence,status,created_at,updated_at,trigger) '
                      'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (uuid.uuid4().hex, org, title, summary, why, offering, size, conf, step, '', json.dumps([f'{site}/news/{k + 1}']), status,
                       (now - timedelta(days=2 + 3 * k)).isoformat(), (now - timedelta(days=1 + k)).isoformat(), 'schedule' if k % 2 else 'you'))
        for k, (org, title, summary) in enumerate(NEWS):
            site = next(o[4] for o in ORGS if o[0] == org)
            c.execute('INSERT INTO org_news(id,org,url,title,published,summary,created_at) VALUES (?,?,?,?,?,?,?)',
                      (uuid.uuid4().hex, org, f'{site}/news/{k + 1}', title, (today - timedelta(days=3 + 4 * k)).isoformat(), summary, store.now()))
        for name, kind, is_client, mgr, site, desc in ORGS:
            freq = 'weekly' if is_client else 'off'
            c.execute('INSERT INTO org_watch(org,frequency,last_run,next_run,last_status,last_summary) VALUES (?,?,?,?,?,?)',
                      (name, freq, (now - timedelta(days=3)).isoformat() if is_client else None,
                       (now + timedelta(days=4)).isoformat() if is_client else None, 'complete' if is_client else '',
                       'Demo data' if is_client else ''))
        store.audit(c, 'demo_seeded', 'demo', 'demo', f'{len(ORGS)} fictional organisations, {n_fact} facts')
