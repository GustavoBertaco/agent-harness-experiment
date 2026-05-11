FROM python:3.11-slim

RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --no-create-home --shell /bin/false appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY producer/ ./producer/

USER appuser

CMD ["python", "-m", "producer.main"]
