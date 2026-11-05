FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY it_support_ticket_triage ./it_support_ticket_triage
COPY scripts ./scripts
RUN python scripts/generate_data.py && pip install --no-cache-dir .
CMD exec uvicorn it_support_ticket_triage.main:app --host 0.0.0.0 --port ${PORT:-8080}
