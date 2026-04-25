FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends wget \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid 10001 --home /app --shell /usr/sbin/nologin app \
    && mkdir -p /app \
    && chown -R app:app /app

WORKDIR /app

COPY --chown=app:app api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app shared/ /app/shared/
COPY --chown=app:app api/src/ /app/api/src/

USER app:app
EXPOSE 8000

CMD ["uvicorn", "api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
