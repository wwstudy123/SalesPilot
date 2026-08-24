FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY sale-agent ./sale-agent
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["python", "-m", "sale_agent.entry.internal_api.run"]
