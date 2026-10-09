"""Every role assignment in infra/*.bicep names a real role (Stefan, 8 Oct 2026: -Step backup failed with
RoleDefinitionDoesNotExist because backup.bicep's Reader ID was not Reader's). Each roleDefinitionId must be built with
subscriptionResourceId('Microsoft.Authorization/roleDefinitions', <id>) from a hyphenated GUID that is one of the built-in
roles below (copied from Microsoft's published list of built-in roles), or be a custom role defined in the same file.
Azure prints role IDs without hyphens in its error messages; the template must always carry the hyphenated form."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INFRA = os.path.join(ROOT, 'infra')

# Microsoft's built-in roles that Alice uses: ID -> name (learn.microsoft.com, Azure built-in roles). Add a role here only
# after checking its ID against that page.
BUILT_IN = {
    'acdd72a7-3385-48ef-bd42-f606fba81ae7': 'Reader',
    'b24988ac-6180-42a0-ab88-20f7382dd24c': 'Contributor',
    '7f951dda-4ed3-4680-a7ca-43fe172d538d': 'AcrPull',
    '4633458b-17de-408a-b874-0445c86b69e6': 'Key Vault Secrets User',
    'b86a8fe4-44ce-4948-aee5-eccb2c155cd7': 'Key Vault Secrets Officer',
    'ba92f5b4-2d11-453d-a403-e96b0029c9fe': 'Storage Blob Data Contributor',
    '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1': 'Storage Blob Data Reader',
    'f1a07417-d97a-45cb-824c-7a7467783830': 'Managed Identity Operator',
}
GUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
BUILT = re.compile(r"^subscriptionResourceId\('Microsoft\.Authorization/roleDefinitions',\s*(.+?)\)$")


def strings(text):
    """name -> literal for `var x = '...'` and the entries of `var x = { k: '...' }` (as x.k)."""
    out = {}
    for m in re.finditer(r"^var (\w+) = '([^']*)'", text, re.M): out[m.group(1)] = m.group(2)
    for m in re.finditer(r'^var (\w+) = \{\n(.*?)^\}', text, re.M | re.S):
        for k, v in re.findall(r"^\s+(\w+): '([^']*)'", m.group(2), re.M): out[f'{m.group(1)}.{k}'] = v
    return out


def role_values(text):
    """Each roleDefinitionId's expression, read up to the first comma or brace outside brackets."""
    out = []
    for m in re.finditer(r'roleDefinitionId:\s*', text):
        i, depth = m.end(), 0
        while i < len(text):
            c = text[i]
            if c in '([': depth += 1
            elif c in ')]': depth -= 1
            elif depth == 0 and c in ',}\n': break
            i += 1
        out.append(text[m.end():i].strip())
    return out


def resolve(expr, names):
    expr = expr.strip()
    if expr.startswith("'") and expr.endswith("'"): return expr[1:-1]
    return names.get(expr)


files = sorted(f for f in os.listdir(INFRA) if f.endswith('.bicep'))
t('roles: the infra templates are found', {'main.bicep', 'backup.bicep', 'drill-access.bicep'} <= set(files))
checked, problems, total = [], [], 0
for name in files:
    text = open(os.path.join(INFRA, name), encoding='utf-8').read()
    names = strings(text)
    custom = set(re.findall(r"^resource (\w+) 'Microsoft\.Authorization/roleDefinitions@", text, re.M))
    total += len(role_values(text))
    for value in role_values(text):
        if value.endswith('.id') and value[:-3] in custom:
            checked.append((name, value, 'custom role')); continue
        m = BUILT.match(value)
        if not m:
            problems.append(f"{name}: {value} is not subscriptionResourceId('Microsoft.Authorization/roleDefinitions', <id>)"); continue
        rid = resolve(m.group(1), names)
        if rid is None: problems.append(f'{name}: {m.group(1)} is not a role ID literal in this file'); continue
        if not GUID.match(rid): problems.append(f'{name}: {m.group(1)} = {rid!r} is not a lower-case hyphenated GUID'); continue
        if rid not in BUILT_IN: problems.append(f'{name}: {m.group(1)} = {rid} is not a known built-in role'); continue
        checked.append((name, m.group(1), BUILT_IN[rid]))
    # No role ID may appear without its hyphens anywhere in a template (the form Azure prints in its errors)
    for bare in re.findall(r"'([0-9a-fA-F]{32})'", text): problems.append(f'{name}: {bare} has no hyphens')
    # Every GUID-shaped literal in a role list is a known role, so a wrong ID cannot sit unused and be picked up later
    for key, v in names.items():
        if GUID.match(v.lower()) and v not in BUILT_IN: problems.append(f'{name}: {key} = {v} is not a known built-in role')

t(f'roles: every role assignment was found and checked ({len(checked)} of {total})', total >= 13 and len(checked) == total)
for p in problems: print('  ' + p)
t('roles: every roleDefinitionId is a known built-in role (hyphenated GUID via subscriptionResourceId) or a custom role in the same file',
  not problems)
t('roles: the Backup page\'s Reader on the vault and the database is the real Reader role',
  sum(1 for f, k, r in checked if f == 'backup.bicep' and k == 'roles.reader' and r == 'Reader') == 2)
t('roles: the known list itself is well formed', all(GUID.match(g) for g in BUILT_IN) and len(set(BUILT_IN.values())) == len(BUILT_IN))

# The check itself catches the mistake that broke -Step backup
bad = "var roles = {\n  reader: 'acdd72a7-3b8d-4880-a14c-c6b6b1c4f1e4'\n}\nx: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.reader), y: 1 }"
n = strings(bad); v = BUILT.match(role_values(bad)[0])
t('roles: the old wrong Reader ID would be refused', resolve(v.group(1), n) not in BUILT_IN)
t('roles: an ID without hyphens would be refused', not GUID.match('acdd72a733854' + '8efbd42f606fba81ae7'))
