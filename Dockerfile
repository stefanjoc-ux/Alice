# Alice: one image, two apps (Azure Container Apps).
#   alice-web  (ALICE_ROLE=web): chat + Command centre on :8000, plus the internal MCP server on 127.0.0.1:8001 (never exposed)
#   alice-mcp  (ALICE_ROLE=mcp): the signed-in external MCP endpoint on :8002 (Entra token on every request)
# Settings come from the environment (Key Vault references in Azure); no secrets in the image. Logs go to stdout.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AISUBSTRATE_DATA_DIR=/mnt/alice/data ALICE_DOCUMENT_LIBRARY=/mnt/alice/Documents ALICE_ROLE=web

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Which release this image is (shown at the bottom of the Command centre menu). Set by the pipeline; 'local' otherwise.
ARG ALICE_VERSION=local
ARG ALICE_BUILT=
ENV ALICE_VERSION=$ALICE_VERSION ALICE_BUILT=$ALICE_BUILT

COPY . .
RUN useradd --create-home --uid 10001 alice && mkdir -p /mnt/alice/data /mnt/alice/Documents \
    && chown -R alice:alice /mnt/alice && chmod +x deploy/start.sh
USER alice

EXPOSE 8000 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD python -c "import os,urllib.request,socket; r=os.environ.get('ALICE_ROLE','web'); \
  (urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=4) if r=='web' else socket.create_connection(('127.0.0.1',int(os.environ.get('ALICE_EXT_PORT','8002'))),4))" || exit 1
CMD ["deploy/start.sh"]
