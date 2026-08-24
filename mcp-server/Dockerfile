FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY sale_server ./sale_server
RUN pip install --no-cache-dir .
EXPOSE 9010
CMD ["python", "-m", "sale_server.run"]
