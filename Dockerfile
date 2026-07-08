FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY migrations ./migrations

RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys, urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3); sys.exit(0 if response.status == 200 else 1)"

CMD ["uvicorn", "src.operator_api.entrypoint:app", "--host", "0.0.0.0", "--port", "8000"]
