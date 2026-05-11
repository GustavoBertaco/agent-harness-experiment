import json
import logging
import signal
import sys
import time

import confluent_kafka

from producer.config import ProducerConfig
from producer.event_generator import generate_event
from producer.rate_limiter import RateLimiter
from producer.schema import build_envelope_schema, make_serializer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_KAFKA_CONFIG = {
    "batch.size": 200000,
    "linger.ms": 100,
    "compression.type": "lz4",
    "queue.buffering.max.messages": 100000,
    "acks": "1",
}


def connect_kafka(bootstrap_servers: str, max_retries: int = 5, base_delay: float = 1.0):
    delays = [base_delay * (2 ** i) for i in range(max_retries)]
    for attempt, delay in enumerate(delays, start=1):
        try:
            producer = confluent_kafka.Producer(
                {"bootstrap.servers": bootstrap_servers, **_KAFKA_CONFIG}
            )
            return producer
        except confluent_kafka.KafkaException as exc:
            logger.warning("Kafka connect attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(delay)
    logger.error("Kafka connection failed after %d attempts — exiting", max_retries)
    sys.exit(1)


def log_startup_summary(
    bootstrap_servers: str,
    topic: str,
    event_rate: int,
    mode: str,
    schema_registry_url: str,
) -> None:
    if schema_registry_url:
        logger.info(
            "Producer started bootstrap_servers=%s topic=%s rate=%d/s mode=%s url=%s",
            bootstrap_servers,
            topic,
            event_rate,
            mode,
            schema_registry_url,
        )
    else:
        logger.info(
            "Producer started bootstrap_servers=%s topic=%s rate=%d/s mode=%s",
            bootstrap_servers,
            topic,
            event_rate,
            mode,
        )


def log_batch_rate(achieved_rate: float) -> None:
    logger.info("batch rate=%.1f/s", achieved_rate)


def check_rate_drift(target_rate: float, achieved_rate: float) -> None:
    if achieved_rate < target_rate * 0.90:
        logger.warning(
            "Rate drift detected: target=%.1f/s achieved=%.1f/s (%.0f%%)",
            target_rate,
            achieved_rate,
            (achieved_rate / target_rate) * 100,
        )


def _run_produce_loop(
    producer,
    config: ProducerConfig,
    schema,
    serializer,
    schema_fields,
    payload_template: dict,
    stop_flag,
) -> None:
    rate_limiter = RateLimiter(config.event_rate)
    ops, weights = config.op_weights.as_choices()
    import random

    pos = 0
    batch_size = max(1, config.event_rate // 10)
    batch_count = 0
    batch_start = time.monotonic()

    while not stop_flag["stop"]:
        import time as _time
        ts_ms = int(_time.time() * 1000)
        op = random.choices(ops, weights=weights, k=1)[0]
        event = generate_event(op, schema_fields, payload_template, pos, ts_ms)
        raw = serializer.serialize(event, schema)
        producer.produce(config.topic, value=raw)
        pos += 1
        batch_count += 1
        rate_limiter.acquire()

        if batch_count >= batch_size:
            elapsed = time.monotonic() - batch_start
            achieved = batch_count / elapsed if elapsed > 0 else 0.0
            log_batch_rate(achieved)
            check_rate_drift(config.event_rate, achieved)
            batch_count = 0
            batch_start = time.monotonic()
            producer.poll(0)


def main() -> None:
    config = ProducerConfig()
    schema = build_envelope_schema(config.payload_template)
    mode = "schema-registry" if config.schema_registry_url else "raw"
    serializer = make_serializer(config, schema)

    log_startup_summary(
        bootstrap_servers=config.bootstrap_servers,
        topic=config.topic,
        event_rate=config.event_rate,
        mode=mode,
        schema_registry_url=config.schema_registry_url,
    )

    producer = connect_kafka(config.bootstrap_servers)

    payload_template = json.loads(config.payload_template)
    from producer.schema import build_row_schema
    schema_fields = build_row_schema(config.payload_template)["fields"]

    stop_flag = {"stop": False}

    def _handle_signal(signum, frame):
        logger.info("Signal %d received — shutting down", signum)
        stop_flag["stop"] = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    _run_produce_loop(producer, config, schema, serializer, schema_fields, payload_template, stop_flag)
    producer.flush()


if __name__ == "__main__":
    main()
