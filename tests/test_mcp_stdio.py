"""Alice's connector exactly as Claude Desktop uses it (stdio): tools, saving conversations, linking, refusals."""
import _util
from _util import t
import asyncio, json, os, sys
import app, temple, substrate_store as s
temple.save_settings(False, 'openai')
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

T = lambda *xs: [{'role': r, 'text': x} for r, x in xs]
async def main():
    transport = StdioTransport(command=sys.executable, args=['mcp_server.py', '--stdio', '--client', 'Claude Desktop'],
                               env=dict(os.environ), cwd=_util.ROOT)
    async with Client(transport) as c:
        names = sorted(x.name for x in await c.list_tools())
        t('all fifteen tools offered', names == ['append_conversation', 'get_health_context', 'get_organisation', 'list_files', 'list_organisations', 'propose_decision',
                                                   'propose_health_note', 'propose_knowledge', 'propose_org_fact', 'propose_record', 'read_file', 'save_conversation',
                                                   'search_files', 'search_opportunities', 'search_records'])
        call = lambda n, a: c.call_tool(n, a)
        await call('propose_knowledge', {'title': 'Accounts briefing', 'content': 'One-page client briefing on the accounts review for the council.', 'source': 'Claude Desktop conversation'})
        r = json.loads((await call('save_conversation', {'title': 'Accounts review', 'summary': 'Reviewed the accounts and drafted a client briefing for the council finance team.',
                        'transcript': T(('user', 'What roof should the carport have?'), ('assistant', 'EPDM or sheets.'), ('user', 'I want light through the roof')),
                        'transcript_complete': False})).content[0].text)
        await call('append_conversation', {'conversation_id': r['id'], 'transcript': T(('assistant', 'Then clear sheets.'), ('user', 'Go with clear sheets'))})
        try:
            await call('append_conversation', {'conversation_id': r['id'], 'transcript': T(('user', 'token ghp_' + 'A' * 36))})
            t('credential in a transcript refused', False)
        except Exception as e:
            t('credential in a transcript refused', 'Secret detection' in str(e))
        await call('propose_decision', {'title': 'Carport roof', 'decision': 'Use clear corrugated sheets', 'source': 'Stefan agreed'})
        return r['id']
cid = asyncio.run(main())
chat = s.get_chat(cid)
t('transcript stored in order, joined across parts', [(x['user_text'][:12], x['reply'][:10]) for x in chat['turns']] ==
  [('What roof sh', 'EPDM or sh'), ('I want light', 'Then clear'), ('Go with clea', '')])
arc = {c['id']: c for c in s.archived_chats(source='external')['chats']}[cid]
t('briefing before and decision after the save are both linked', arc['knowledge'] == 1 and arc['memories'] == 1 and arc['captured'])
