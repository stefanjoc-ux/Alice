"""Apps: things built on Alice that do a job end to end (Mileage Clerk first; expenses, purchase-to-pay slices and others
later). Each app has its own page under the Apps area instead of a slot in the menu, and declares what is waiting for
you so the Apps page and the Actions page can show it. Adding an app = one entry in APPS plus its page.

An app's approvals stay on its own page (they need the full detail, e.g. the exact mileage entry); Actions only links
to them, so there is still one place to see everything that needs you.
"""


def _mileage_waiting():
    import mileage
    return mileage.waiting()


def _mileage_summary():
    import mileage
    return mileage.tile()


def _trading_waiting():
    import trading
    return trading.waiting()


def _trading_summary():
    import trading
    return trading.tile()


def _health_waiting():
    import health
    return health.waiting()


def _health_summary():
    import health
    return health.tile()


APPS = [
    {'id': 'mileage', 'name': 'Mileage', 'mark': 'Mi', 'page': 'mileage', 'agent': 'Mileage Clerk',
     'description': 'Business mileage for TMC from your vehicle tracker export: classify places, approve each exact entry.',
     'waiting': _mileage_waiting, 'summary': _mileage_summary},
    {'id': 'trading', 'name': 'Trading desk', 'mark': 'Td', 'page': 'trading', 'agent': 'Trading desk',
     'description': 'Paper trading and algo signals: simulated buys and sells, "what if I had sold" against holding, and how each signal turned out. Simulation only.',
     'waiting': _trading_waiting, 'summary': _trading_summary},
    {'id': 'health', 'name': 'Health Insights', 'mark': 'Hi', 'page': 'health', 'agent': 'Health Insights: report reader',
     'description': 'Blood results from your Thriva reports: trends against the lab\'s ranges, what you are tracking, and a health context Claude and GPT can read when you ask. Informational, not a diagnosis.',
     'waiting': _health_waiting, 'summary': _health_summary},
]
PAGES = {a['page'] for a in APPS}
PERSONAL = {'mileage', 'trading', 'health'}       # The owner's own apps: never shown on the demo Alice


def shown():
    import demo_instance
    return [a for a in APPS if not (demo_instance.ON and a['id'] in PERSONAL)]


def by_page(page):
    return next((a for a in APPS if a['page'] == page), None)


def waiting():
    """Every app's waiting items: [{'app', 'title', 'detail', 'href'}]. An app that fails to answer is skipped, never fatal."""
    out = []
    for a in shown():
        try: items = a['waiting']() or []
        except Exception: items = []
        for i in items: out.append({'app': a['name'], 'title': i['title'], 'detail': i.get('detail', ''), 'href': i.get('href') or '/admin/' + a['page']})
    return out


def summary(a):
    """An app's headline figures for its tile ({stats, spark, note}); optional, and a failure never breaks the page."""
    try: return a['summary']() if a.get('summary') else None
    except Exception: return None


def listing():
    items = waiting()
    return [{'id': a['id'], 'name': a['name'], 'mark': a['mark'], 'description': a['description'], 'href': '/admin/' + a['page'],
             'agent': a['agent'], 'waiting': sum(1 for i in items if i['app'] == a['name']), 'summary': summary(a)} for a in shown()]
