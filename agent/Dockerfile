FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY lookout_agent/ ./lookout_agent/
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

RUN useradd --create-home --uid 1000 agentuser \
    && chown -R agentuser:agentuser /app
USER agentuser

CMD ["lookout-agent"]
