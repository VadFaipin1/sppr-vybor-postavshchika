# Образ компонента: только интерпретатор, драйвер базы и сам пакет
FROM python:3.13-slim

RUN pip install --no-cache-dir "psycopg[binary]==3.3.8" \
 && useradd --create-home sppr \
 && mkdir -p /app/out /app/config && chown sppr /app/out

WORKDIR /app
COPY src/sppr ./sppr
USER sppr

ENTRYPOINT ["python", "-m", "sppr"]
CMD ["check"]
