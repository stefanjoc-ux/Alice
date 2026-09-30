"""Temple's quote check: forgiving about typography, strict about words."""
import _util
from _util import t
import substrate_store as s

msgs = ["We don't want the Borders proposal to lead on price — lead on the tenant consolidation story instead.",
        "Can you draft the agenda for Thursday?"]
for q, expect, label in [
        ("We don’t want the Borders proposal to lead on price", True, 'curly apostrophe'),
        ("lead on price... lead on the tenant consolidation story", True, 'ellipsis join'),
        ("lead on price … consolidation story", True, 'unicode ellipsis'),
        ("WE DON'T WANT THE BORDERS PROPOSAL", True, 'capitals'),
        ("Lead on the tenant consolidation story instead.", True, 'punctuation'),
        ("draft the agenda for Thursday", True, 'found in another message'),
        ("We want to lead on price", False, 'reworded'),
        ("lead on price... cheapest bid wins", False, 'one invented fragment'),
        ("the", False, 'too short to count'),
        ("Here is the agenda", False, "assistant's words")]:
    t(label, (s.quote_found(q, msgs) >= 0) == expect)
