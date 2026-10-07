"""Client material follows the Rules page, never a hard-coded exclusion. Client-facing documents (Parker's proposals, their
reference documents, digital team outputs marked client-facing) follow the rule "Client-facing documents use only that client's
material" (client_documents, on by default); other digital team jobs follow Client separation. Each with its rule on and off;
defaults unchanged. No real model is called."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import substrate_store as s
s.init()
import app, clients as C, knowledge, rules_engine as RE, assistants, proposals, teams, team_qs
teams.BACKGROUND = False

C.create_client('Fictional North Council')
C.create_client('Fictional South Council')
s.create_category('Cost data')


def note(title, text, client=''):
    fid = knowledge.create('note', title, text, 'Fictional source', 'you', category='Cost data')['id']
    if client: C.tag('file', [fid], client)
    return fid


note('General hall guidance (fictional)', 'Fictional general guidance on community hall costs and finishes.')
note('North hall guidance (fictional)', 'Fictional North-only guidance on community hall costs and finishes.', 'Fictional North Council')
note('South hall guidance (fictional)', 'Fictional South-only guidance on community hall costs and finishes.', 'Fictional South Council')
note('South past rates (fictional)', 'Fictional South scheme.\nRATE | S1 | Strip foundations | m | 150 | library | South book | 2025-02', 'Fictional South Council')
note('General past rates (fictional)', 'Fictional general scheme.\nRATE | G1 | Strip foundations | m | 140 | library | General book | 2025-01')

rule = RE.rule('client_documents')
t('the new rule exists in the Organisation set, enforced and on by default', rule and rule['set_key'] == 'organisation' and rule['kind'] == 'enforced'
  and rule['enabled'] and rule['name'] == 'Client-facing documents use only that client\'s material')
t('it is listed on the Rules page', 'client_documents' in [r['id'] for r in RE.all_rules()])


def blocks(rid):
    with s.db() as c: return c.execute("SELECT count(*) FROM activity WHERE action='rule_blocked' AND rule=?", (rid,)).fetchone()[0]


# ---------------- Parker's proposals (client-facing): the new rule decides ----------------
writer = assistants.get('proposal-writer')
def ctx(client):
    text, used, _ = proposals.gather(writer, 'Community hall cost plan', 'hall costs and finishes guidance', client, client)
    return text
b0 = blocks('client_documents')
x = ctx('Fictional North Council')
t('default (rule on): a North proposal gets General and North material, never South', 'General hall guidance' in x and 'North hall guidance' in x and 'South hall guidance' not in x)
t('…and what was left out is logged as a block of that rule', blocks('client_documents') > b0)
y = ctx('')
t('default: a proposal with no client gets General material only', 'General hall guidance' in y and 'North hall guidance' not in y and 'South hall guidance' not in y)
RE.update_rule('client_separation', enabled=False)
t('the Client separation switch does not change client-facing documents', 'South hall guidance' not in ctx('Fictional North Council'))
RE.update_rule('client_separation', enabled=True)
RE.update_rule('client_documents', enabled=False)
x = ctx('Fictional North Council')
t('rule switched off: other clients\' material is no longer excluded from a proposal', 'South hall guidance' in x and 'North hall guidance' in x)
RE.update_rule('client_documents', enabled=True)

# ---------------- Digital teams ----------------
TID = team_qs.TEAM_ID
t('the seeded Cost estimate is client-facing', teams.get(TID)['job_types'][0]['client_facing'] is True)
lead = dict(teams.get(TID)['members'][0], categories=['Cost data'])
trends = teams.get(TID)['members'][3]


def job(client, jt='cost-estimate'):
    return {'id': 'x', 'team_id': TID, 'team_version': teams.get(TID)['current_version'], 'job_type': jt, 'title': 'hall costs',
            'brief': 'community hall costs finishes guidance', 'client': client}


def kn(j): return teams._knowledge(j, lead, 'claude')
def hist(j): return {h['source'] for h in team_qs.history(j, trends)}


x = kn(job('Fictional North Council'))
t('client-facing team job (default): General and its own client only', 'General hall guidance' in x and 'North hall guidance' in x and 'South hall guidance' not in x)
t('…Market Trends past rates likewise', hist(job('Fictional North Council')) == {'General past rates (fictional)'})
RE.update_rule('client_separation', enabled=False)
t('client-facing: the Client separation switch does not change it', 'South hall guidance' not in kn(job('Fictional North Council')))
RE.update_rule('client_separation', enabled=True)
RE.update_rule('client_documents', enabled=False)
t('client-facing, rule switched off: other clients\' knowledge and past rates are used', 'South hall guidance' in kn(job('Fictional North Council'))
  and 'South past rates (fictional)' in hist(job('Fictional North Council')))
RE.update_rule('client_documents', enabled=True)

# a job type that is not client-facing follows Client separation
r = teams.update_job_type(TID, 'cost-estimate', client_facing=False)
t('the client-facing flag is set on the page and versioned', r['job_types'][0]['client_facing'] is False and 'no longer client-facing' in teams.versions(TID)[0]['what'])
x = kn(job('Fictional North Council'))
t('internal job, Client separation on: its own client and General, not another client', 'North hall guidance' in x and 'South hall guidance' not in x)
t('…past rates likewise', 'South past rates (fictional)' not in hist(job('Fictional North Council')))
b1 = blocks('client_separation')
kn(job('Fictional North Council'))
t('…logged as a Client separation block', blocks('client_separation') > b1)
y = kn(job(''))
t('internal job with no client, Client separation not strict: client material may be used (the rule\'s own setting)', 'South hall guidance' in y)
RE.update_rule('client_separation', new_params={'strict': True, 'external': 'all'})
t('…strict: General only', 'South hall guidance' not in kn(job('')) and 'General hall guidance' in kn(job('')))
RE.update_rule('client_separation', new_params={'strict': False, 'external': 'all'})
RE.update_rule('client_documents', enabled=False)
t('internal job: the client-facing rule does not change it', 'South hall guidance' not in kn(job('Fictional North Council')))
RE.update_rule('client_documents', enabled=True)
RE.update_rule('client_separation', enabled=False)
x = kn(job('Fictional North Council'))
t('internal job, Client separation switched off: other clients\' material is used', 'South hall guidance' in x
  and 'South past rates (fictional)' in hist(job('Fictional North Council')))
RE.update_rule('client_separation', enabled=True)
teams.update_job_type(TID, 'cost-estimate', client_facing=True)
t('defaults back: client-facing again', teams.client_facing(job('Fictional North Council')))
t('team versions saved before the flag existed: the cost plan still counts as client-facing, other job types do not',
  teams.facing({'finish': 'cost_estimate'}) and not teams.facing({'finish': ''}))

# ---------------- Parker's reference documents (client-facing) ----------------
import tempfile
from pathlib import Path
import doc_library as L, references as RF
L.ROOT = (Path(tempfile.mkdtemp(prefix='alice-docs-')) / 'Documents').resolve()
L.add_source('SharePoint', 'sharepoint', 'SharePoint Online')
L.save('SharePoint', 'South method.md', b'# South method\n\nFictional South-only method for community hall cost planning and finishes.')
k = knowledge.create('note', 'South method summary (fictional)', 'Fictional summary of the South-only method for hall costs and finishes.',
                     'Summary; full document: SharePoint/South method.md', 'you')['id']
C.tag('file', [k], 'Fictional South Council')
def refs(client):
    text, used, skipped = RF.context(['SharePoint/South method.md'], 'hall costs finishes', client, ['claude'])
    return text, skipped
text, skipped = refs('Fictional North Council')
t('default: a reference document summarised for another client is left out of a proposal', any('tagged to another client' in x for x in skipped) and 'South-only' not in text)
RE.update_rule('client_documents', enabled=False)
text, skipped = refs('Fictional North Council')
t('rule switched off: it is used', not any('tagged to another client' in x for x in skipped) and 'South-only' in text)
RE.update_rule('client_documents', enabled=True)
