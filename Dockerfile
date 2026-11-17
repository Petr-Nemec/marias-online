# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --require-virtualenv=false -r requirements.txt

COPY marias ./marias

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin marias
USER marias

# Listen on all interfaces inside the container; publish the port only to the reverse proxy.
ENV MARIAS_HOST=0.0.0.0 \
    MARIAS_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

CMD ["python", "-m", "marias.server"]
