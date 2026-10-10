"""Where Alice's container images come from: Docker's official images through Amazon's public mirror of them, never Docker Hub
directly (GitHub's runners share Docker Hub's anonymous pull limit; on 9 Oct 2026 pull requests failed before any test ran).
Reads the Dockerfile and the workflows in .github/workflows."""
import _util  # first: throwaway data folder, dummy keys, no real model calls
from _util import t
import re
from pathlib import Path

ROOT = Path(_util.ROOT)
MIRROR = 'public.ecr.aws/docker/library/'

froms = re.findall(r'^\s*FROM\s+(\S+)', (ROOT / 'Dockerfile').read_text(encoding='utf-8'), re.M | re.I)
t('the Dockerfile builds from an image', len(froms) >= 1)
t('…pulled from the public mirror of Docker\'s official images, not Docker Hub', all(f.startswith(MIRROR) for f in froms))

images = []
for wf in sorted((ROOT / '.github' / 'workflows').glob('*.yml')):
    images += [(wf.name, m) for m in re.findall(r'^\s*image:\s*["\']?([^\s"\'#]+)', wf.read_text(encoding='utf-8'), re.M)]
t('the test workflow\'s PostgreSQL service comes from the mirror', ('deploy.yml', MIRROR + 'postgres:16') in images)
t('no workflow pulls a bare Docker Hub image', all('.' in img.split('/')[0] and not img.startswith('docker.io/') for _, img in images))
