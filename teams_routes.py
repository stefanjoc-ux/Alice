"""HTTP routes for Digital teams (the Teams page). Non-GET routes sit under /admin/api, so the admin token and same-origin checks
in app.py's protect_admin middleware apply to every change."""
import asyncio
import base64

from fastapi import APIRouter, HTTPException, Path as FPath, Query
from pydantic import BaseModel, Field

import teams
import team_qs

router = APIRouter()
ID = r'^[A-Za-z0-9_-]{1,80}$'
HEX = r'^[0-9a-f]{32}$'


def _do(fn, *a, **k):
    try: return fn(*a, **k)
    except LookupError as e: raise HTTPException(404, str(e)) from None
    except ValueError as e: raise HTTPException(400, str(e)) from None


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field('', max_length=600)
    colour: str = Field('', max_length=20)
    icon: str = Field('', max_length=20)
    discipline: str = Field('', max_length=60)
    template: str = Field('', max_length=40)


class IdentityIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=600)
    colour: str | None = Field(None, max_length=20)
    icon: str | None = Field(None, max_length=20)
    discipline: str | None = Field(None, max_length=60)


class PinIn(BaseModel):
    on: bool = True


class RateEntry(BaseModel):
    ref: str = Field(min_length=1, max_length=20)
    rate: float | None = None
    unpriced: bool = False


class RatesDecisionIn(BaseModel):
    entries: list[RateEntry] = Field(max_length=500)
    save_to_library: bool = True
    go_on: bool = False


class TalkJobIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    job: str = Field('', pattern=r'^([0-9a-f]{32})?$')


class AutonomyIn(BaseModel):
    autonomy: str = Field(pattern='^(approve|signoff)$')


class SettingsIn(BaseModel):
    settings: dict


class MemberIn(BaseModel):
    role: str | None = Field(None, max_length=80)
    purpose: str | None = Field(None, max_length=600)
    instructions: str | None = Field(None, max_length=6000)
    provider: str | None = Field(None, max_length=40)
    categories: list[str] | None = Field(None, max_length=20)
    packs: list[str] | None = Field(None, max_length=10)


class StageIn(BaseModel):
    key: str = Field('', max_length=40)
    title: str = Field(max_length=80)
    member: str = Field(max_length=40)
    task: str = Field('', max_length=2000)
    hands: str = Field('', max_length=600)
    checks: str = Field('', max_length=1000)


class JobTypeIn(BaseModel):
    name: str | None = Field(None, max_length=80)
    description: str | None = Field(None, max_length=600)
    stages: list[StageIn] | None = Field(None, max_length=12)
    client_facing: bool | None = None


class RestoreIn(BaseModel):
    version: int = Field(0, ge=0)
    undo: bool = False


class TalkIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class DecideIn(BaseModel):
    action: str = Field(pattern='^(approve|send_back|answer|reject)$')
    note: str = Field('', max_length=2000)


class UploadIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field('brief', max_length=20)
    data: str | None = Field(None, max_length=21_000_000)
    text: str | None = Field(None, max_length=400_000)


class PickIn(BaseModel):
    path: str = Field(min_length=1, max_length=400)
    kind: str = Field('spec', max_length=20)


class JobIn(BaseModel):
    job_type: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=150)
    brief: str = Field(min_length=1, max_length=20000)
    location: str = Field('', max_length=120)
    client: str = Field('', max_length=80)
    uploads: list[UploadIn] = Field(default_factory=list, max_length=12)
    library: list[PickIn] = Field(default_factory=list, max_length=12)


class RatesIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    data: str = Field(min_length=1, max_length=21_000_000)
    label: str = Field('', max_length=120)


# ---------------- fixed paths first (before /teams/{tid}) ----------------
@router.get('/admin/api/teams')
def teams_home():
    rows = teams.listing()
    return _do(teams.overview, rows[0]['id']) if rows else {'teams': [], 'team': None}


@router.post('/admin/api/teams')
def teams_create(t: TeamIn):
    if t.template: return _do(teams.from_template, t.template, t.name, t.description, t.colour, t.icon, t.discipline)
    return _do(teams.create, t.name, t.description, colour=t.colour, icon=t.icon, discipline=t.discipline)


@router.get('/admin/api/teams/board')
def teams_board():
    """All teams: summary, what needs you across teams, one entry per team (the All teams page)."""
    return teams.board()


@router.get('/admin/api/teams/demo-project')
def teams_demo_project():
    return _do(team_qs.demo_project)


@router.get('/admin/api/teams/library-files')
def teams_library_files():
    """Documents in the document sources that a job can point to (names and paths only; nothing is read)."""
    import doc_library
    out = []
    for s in doc_library.sources():
        if not s['id']: continue
        try: out += [{'path': f['path'], 'name': f['name'], 'source': s['name']} for f in doc_library.files(s['id'], labels=False, summaries=False)]
        except ValueError: continue
    return {'files': out[:500]}


@router.post('/admin/api/teams/suggestions/{sid}')
def teams_suggestion(d: DecideIn, sid: str = FPath(pattern=HEX)):
    if d.action not in ('approve', 'reject'): raise HTTPException(400, 'Approve or reject.')
    return _do(teams.decide_suggestion, sid, d.action)


@router.get('/admin/api/teams/jobs/{jid}')
def teams_job(jid: str = FPath(pattern=HEX)):
    return _do(teams.job_detail, jid)


@router.get('/admin/api/teams/jobs/{jid}/page')
def teams_job_page(jid: str = FPath(pattern=HEX)):
    return _do(teams.job_page, jid)


@router.post('/admin/api/teams/jobs/{jid}/rates')
def teams_job_rates(d: RatesDecisionIn, jid: str = FPath(pattern=HEX)):
    return _do(team_qs.decide_rates, jid, [e.model_dump() for e in d.entries], d.save_to_library, d.go_on)


@router.post('/admin/api/teams/jobs/{jid}/resume')
def teams_job_resume(jid: str = FPath(pattern=HEX)):
    return _do(teams.resume, jid)


@router.post('/admin/api/teams/jobs/{jid}/stop')
def teams_job_stop(jid: str = FPath(pattern=HEX)):
    return _do(teams.stop, jid)


@router.post('/admin/api/teams/steps/{sid}')
def teams_step(d: DecideIn, sid: str = FPath(pattern=HEX)):
    return _do(teams.decide, sid, d.action, d.note)


# ---------------- one team ----------------
@router.get('/admin/api/teams/{tid}')
def teams_one(tid: str = FPath(pattern=ID)):
    return _do(teams.overview, tid)


@router.get('/admin/api/teams/{tid}/page')
def teams_page(tid: str = FPath(pattern=ID)):
    return _do(teams.page, tid)


@router.post('/admin/api/teams/{tid}/seen')
def teams_seen(tid: str = FPath(pattern=ID)):
    return _do(teams.seen, tid)


@router.put('/admin/api/teams/{tid}/pin')
def teams_pin(p: PinIn, tid: str = FPath(pattern=ID)):
    return _do(teams.set_pin, tid, p.on)


@router.put('/admin/api/teams/{tid}/identity')
def teams_identity(i: IdentityIn, tid: str = FPath(pattern=ID)):
    return _do(teams.set_identity, tid, i.name, i.description, i.colour, i.icon, i.discipline)


@router.get('/admin/api/teams/{tid}/talk')
def teams_talk_history(tid: str = FPath(pattern=ID), job: str = Query('', pattern=r'^([0-9a-f]{32})?$')):
    return {'messages': _do(teams.messages, tid, job)}


@router.post('/admin/api/teams/{tid}/talk')
async def teams_talk(q: TalkJobIn, tid: str = FPath(pattern=ID)):
    try: return await asyncio.to_thread(teams.talk, tid, q.job, q.message)
    except LookupError as e: raise HTTPException(404, str(e)) from None
    except ValueError as e: raise HTTPException(400, str(e)) from None


@router.put('/admin/api/teams/{tid}/autonomy')
def teams_autonomy(a: AutonomyIn, tid: str = FPath(pattern=ID)):
    return _do(teams.set_autonomy, tid, a.autonomy)


@router.put('/admin/api/teams/{tid}/settings')
def teams_settings(s: SettingsIn, tid: str = FPath(pattern=ID)):
    return _do(teams.set_settings, tid, s.settings)


@router.post('/admin/api/teams/{tid}/members')
def teams_member_add(m: MemberIn, tid: str = FPath(pattern=ID)):
    return _do(teams.add_member, tid, m.model_dump(exclude_none=True))


@router.put('/admin/api/teams/{tid}/members/{mid}')
def teams_member_update(m: MemberIn, tid: str = FPath(pattern=ID), mid: str = FPath(pattern=ID)):
    return _do(teams.update_member, tid, mid, m.model_dump(exclude_none=True))


@router.delete('/admin/api/teams/{tid}/members/{mid}')
def teams_member_remove(tid: str = FPath(pattern=ID), mid: str = FPath(pattern=ID)):
    return _do(teams.remove_member, tid, mid)


@router.post('/admin/api/teams/{tid}/job-types')
def teams_job_type_add(t: TeamIn, tid: str = FPath(pattern=ID)):
    return _do(teams.add_job_type, tid, t.name, t.description)


@router.put('/admin/api/teams/{tid}/job-types/{jt}')
def teams_job_type(j: JobTypeIn, tid: str = FPath(pattern=ID), jt: str = FPath(pattern=ID)):
    return _do(teams.update_job_type, tid, jt, j.name, j.description, [s.model_dump() for s in j.stages] if j.stages is not None else None,
               j.client_facing)


@router.post('/admin/api/teams/{tid}/restore')
def teams_restore(r: RestoreIn, tid: str = FPath(pattern=ID)):
    return _do(teams.restore, tid, r.version, r.undo)


@router.get('/admin/api/teams/{tid}/members/{mid}/discussion')
def teams_member_talk_history(tid: str = FPath(pattern=ID), mid: str = FPath(pattern=ID)):
    return {'messages': _do(teams.coach_history, tid, mid)}


@router.post('/admin/api/teams/{tid}/members/{mid}/discussion')
async def teams_member_talk(q: TalkIn, tid: str = FPath(pattern=ID), mid: str = FPath(pattern=ID)):
    import provider_errors
    try: return await asyncio.to_thread(teams.coach, tid, mid, q.message)
    except ValueError as e: raise HTTPException(400, str(e)) from None
    except Exception as e:
        if provider_errors.is_provider_error(e): raise HTTPException(502, 'Temple: ' + provider_errors.message(e, log='Temple team refinements')) from None
        raise


@router.post('/admin/api/teams/{tid}/jobs')
def teams_job_start(j: JobIn, tid: str = FPath(pattern=ID)):
    return _do(teams.start_job, tid, j.job_type, j.title, j.brief, j.location, j.client,
               [u.model_dump() for u in j.uploads], [p.model_dump() for p in j.library])


@router.get('/admin/api/teams/{tid}/rates')
def teams_rates(tid: str = FPath(pattern=ID)):
    return {'rates': _do(team_qs.library, tid)}


@router.post('/admin/api/teams/{tid}/rates')
def teams_rates_add(r: RatesIn, tid: str = FPath(pattern=ID)):
    try: raw = base64.b64decode(r.data, validate=True)
    except ValueError: raise HTTPException(400, 'The file could not be read.') from None
    return _do(team_qs.import_rates, tid, r.name, raw, r.label)


@router.post('/admin/api/teams/{tid}/rates/demo')
def teams_rates_demo(tid: str = FPath(pattern=ID)):
    return _do(team_qs.load_demo_rates, tid)


@router.delete('/admin/api/teams/{tid}/rates/{batch}')
def teams_rates_remove(tid: str = FPath(pattern=ID), batch: str = FPath(pattern=r'^[0-9a-f]{12}$')):
    return _do(team_qs.remove_rates, tid, batch)
