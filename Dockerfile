FROM python:3.11.15-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Apply Debian security updates available at image-build time. Trivy scans the
# exact resolved image after this layer and the workflow blocks HIGH/CRITICAL
# findings with a machine-readable policy step.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade \
        pip \
        "setuptools>=83.0.0,<84.0.0" \
        "wheel>=0.46.2,<0.47.0" \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip install --no-cache-dir --upgrade \
        "msgpack>=1.2.1,<2.0.0" \
        "setuptools>=83.0.0,<84.0.0"

COPY src ./src
COPY migrations ./migrations
COPY web ./web
COPY docs/operations/P100_ACCEPTANCE_PILOT_RUNBOOK.md ./docs/operations/P100_ACCEPTANCE_PILOT_RUNBOOK.md

RUN useradd --create-home --shell /usr/sbin/nologin appuser
# Keep security-fixed Python bootstrap packages in the final runtime image.
RUN python -m pip install --no-cache-dir --upgrade \
    "msgpack==1.2.1" \
    "setuptools==83.0.0" \
    && python -c "import importlib.metadata as m; assert m.version('msgpack') == '1.2.1'; assert m.version('setuptools') == '83.0.0'"
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys, urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3); sys.exit(0 if response.status == 200 else 1)"

CMD ["uvicorn", "src.operator_api.entrypoint:app", "--host", "0.0.0.0", "--port", "8000"]
