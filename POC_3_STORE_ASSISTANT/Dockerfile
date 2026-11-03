FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY store_assistant ./store_assistant
RUN pip install --no-cache-dir .
CMD exec uvicorn store_assistant.main:app --host 0.0.0.0 --port ${PORT:-8080}
