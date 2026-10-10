# Alice: one image, two apps (Azure Container Apps).
#   alice-web  (ALICE_ROLE=web): chat + Command centre on :8000, plus the internal MCP server on 127.0.0.1:8001 (never exposed)
#   alice-mcp  (ALICE_ROLE=mcp): the signed-in external MCP endpoint on :8002 (Entra token on every request)
#   alice-backup (ALICE_ROLE=backup): the nightly off-site copy, a Container Apps job
# Settings come from the environment (Key Vault references in Azure); no secrets in the image. Logs go to stdout.
# Docker's official images are pulled from Amazon's public mirror of them (the same images, byte for byte), never from Docker Hub
# directly: GitHub's runners share Docker Hub's anonymous pull limit and were refused (9 Oct 2026). tests/test_image_sources.py checks it.
FROM public.ecr.aws/docker/library/python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AISUBSTRATE_DATA_DIR=/mnt/alice/data ALICE_DOCUMENT_LIBRARY=/mnt/alice/Documents ALICE_ROLE=web

WORKDIR /app
# pg_dump for the nightly off-site backup (backup.py, role backup). Debian's client is newer than the server (16), which pg_dump supports.
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt

# Which release this image is (shown at the bottom of the Command centre menu). Set by the pipeline; 'local' otherwise.
ARG ALICE_VERSION=local
ARG ALICE_BUILT=
# Where its code lives, for the commit and pull request links (deployment.py; set by the pipeline, never written in the code).
ARG ALICE_REPO_URL=
ENV ALICE_VERSION=$ALICE_VERSION ALICE_BUILT=$ALICE_BUILT ALICE_REPO_URL=$ALICE_REPO_URL

COPY . .
RUN useradd --create-home --uid 10001 alice && mkdir -p /mnt/alice/data /mnt/alice/Documents \
    && chown -R alice:alice /mnt/alice && chmod +x deploy/start.sh
USER alice

EXPOSE 8000 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD python -c "import os,urllib.request,socket; r=os.environ.get('ALICE_ROLE','web'); \
  (urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=4) if r=='web' else socket.create_connection(('127.0.0.1',int(os.environ.get('ALICE_EXT_PORT','8002'))),4))" || exit 1
CMD ["deploy/start.sh"]
