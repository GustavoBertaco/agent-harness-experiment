# ENG-01: Python CDC Event Producer

**Wave:** 1
**Depends on:** none

## Overview

Implement the core Python 3.12 event producer that generates synthetic Debezium CDC-style Avro events and publishes them to a Kafka topic at a configurable rate. This module is entirely self-contained: it reads configuration from environment variables, handles Avro serialization in two modes (raw and Schema Registry wire format), manages the publish loop with rate control, and emits structured log lines throughout. All behavior is covered by pytest tests written before any implementation code.

## Tech Choices

- Language: Python 3.12
- Kafka client: `confluent-kafka-python` — chosen over `kafka-python` because it ships native librdkafka bindings (lower latency, better throughput at 100 events/sec), has first-class Avro + Schema Registry support via `confluent-kafka[avro]`, and is actively maintained by Confluent. `kafka-python` would require a separate Avro library and has no native Schema Registry client.
- Avro serialization: `fastavro` for raw Avro mode; `confluent-kafka[avro]` (SchemaRegistryClient + AvroSerializer) for Schema Registry wire format mode
- Test runner: `pytest` with `pytest-mock` for unit tests; no live Kafka or Schema Registry required for unit tests (mock at the confluent-kafka Producer boundary)
- Linting/types: `mypy` (strict), `ruff`

## File Layout

All files under `experiments/k8s-event-generator/`:

```
experiments/k8s-event-generator/
├── producer/
│   ├── __init__.py
│   ├── schema.py          ← Avro schema definition + fastavro helpers
│   ├── event.py           ← event factory (builds CDC envelope dicts)
│   ├── serializer.py      ← raw Avro vs. Schema Registry wire format
│   ├── publisher.py       ← Kafka producer wrapper + rate-controlled loop
│   └── config.py          ← env-var parsing + validation
├── tests/
│   ├── __init__.py
│   ├── test_schema.py
│   ├── test_event.py
│   ├── test_serializer.py
│   ├── test_publisher.py
│   └── test_config.py
├── requirements.txt
└── main.py                ← entrypoint: reads config, wires modules, starts loop
```

## Implementation Steps

Follow TDD strictly: write failing test → minimum code to pass → refactor.

1. **`config.py`** — Parse and validate env vars. Required: `KAFKA_BOOTSTRAP_SERVERS`. Optional with defaults: `KAFKA_TOPIC` (`cdc-events`), `EVENT_RATE_PER_SEC` (100), `SCHEMA_REGISTRY_URL` (empty = raw mode), `PAYLOAD_TEMPLATE` (built-in synthetic record). Raise `ValueError` with a clear message for missing required vars or invalid types.
2. **`schema.py`** — Define the Debezium CDC Avro schema as a Python dict matching PS-001 §Event Payload Format exactly. Expose a `parse_schema()` function returning a parsed fastavro schema. No I/O in this module.
3. **`event.py`** — `EventFactory` class with a `build(op="c")` method that returns a fully-populated CDC envelope dict: `after.id` = UUID v4, `after.text` = 32-char random alphanumeric, `after.created_at` = epoch ms, `ts_ms` = epoch ms, `source.name` = topic name, `source.db` = `"synthetic"`, `source.table` = `"events"`. `before` = null for `op="c"`.
4. **`serializer.py`** — `Serializer` base + two subclasses: `RawAvroSerializer` (fastavro bytes, no prefix) and `SchemaRegistrySerializer` (magic byte 0x00 + 4-byte schema ID + fastavro bytes). `SchemaRegistrySerializer.__init__` contacts Schema Registry to register/fetch the schema ID; if unreachable, raises `ConnectionError` with the URL in the message.
5. **`publisher.py`** — `Publisher` class wrapping `confluent_kafka.Producer`. `publish_loop(factory, serializer, config)` runs indefinitely: builds event, serializes, produces to Kafka, sleeps to hit target rate. Tracks achieved rate over a 1-second window. Logs startup confirmation, per-second rate (INFO), and rate drift warnings (WARN) when achieved < 90% of target. On Kafka delivery error after 5 retries with exponential backoff, logs ERROR and raises.
6. **`main.py`** — Wire all modules: parse config, select serializer mode, construct factory and publisher, call publish loop. On `ConnectionError` from serializer init, log the error and `sys.exit(1)`. On Kafka failure after retries, log and `sys.exit(1)`.
7. **`requirements.txt`** — Pin `confluent-kafka[avro]`, `fastavro`, `pytest`, `pytest-mock`, `mypy`, `ruff`.

## Test Plan

All tests in `experiments/k8s-event-generator/tests/`. Run with:

```
pytest experiments/k8s-event-generator/tests/ -v
```

Unit tests only — no live Kafka or Schema Registry required:

| Test file | Key tests |
|-----------|-----------|
| `test_config.py` | Valid env → Config object; missing `KAFKA_BOOTSTRAP_SERVERS` → ValueError; invalid `EVENT_RATE_PER_SEC` (non-int) → ValueError; `SCHEMA_REGISTRY_URL` empty → schema_registry_mode=False |
| `test_schema.py` | `parse_schema()` returns a valid fastavro schema; schema has all required fields from PS-001 |
| `test_event.py` | `build("c")` returns dict with non-null `after`, null `before`; `after.id` is valid UUID v4; `after.text` is 32 chars; `ts_ms` is close to epoch ms now; `build("d")` has null `after`, non-null `before` |
| `test_serializer.py` | `RawAvroSerializer.serialize(event)` returns bytes deserializable by fastavro; `SchemaRegistrySerializer.__init__` with unreachable URL raises `ConnectionError`; wire format bytes start with 0x00 followed by 4-byte int (mocked schema ID) |
| `test_publisher.py` | `publish_loop` calls `producer.produce` at least once per iteration (mock producer); rate drift warning logged when mock clock shows achieved rate < 90% of target; on delivery error after 5 retries, raises |

## Acceptance Criteria

Maps to PS-001 AC-7 (pytest green) and portions of AC-1, AC-2, AC-5, AC-6:

- AC-7: `pytest experiments/k8s-event-generator/tests/ -v` → 0 failures, 0 errors
- AC-2 (unit): `RawAvroSerializer` does not instantiate any Schema Registry client when `SCHEMA_REGISTRY_URL` is unset
- AC-5 (unit): `publish_loop` emits at least one startup INFO log and one per-second rate INFO log per publish cycle
- AC-6 (unit): When `SCHEMA_REGISTRY_URL` is set to an invalid host, `SchemaRegistrySerializer.__init__` raises `ConnectionError`; `main.py` catches it, logs the error, and exits with code 1

## Notes

- Do not mock fastavro — use the real library in tests. Mock only at the `confluent_kafka.Producer` boundary and at the HTTP boundary for Schema Registry.
- `confluent_kafka.Producer` is a C extension; use `pytest-mock` to patch `confluent_kafka.Producer` in publisher tests.
- Rate control: use `time.perf_counter()` for the achieved-rate calculation window, not `time.time()`.
- The `PAYLOAD_TEMPLATE` env var is reserved for v2 — parse it in `config.py` but ignore its value in the event factory (always use built-in synthetic record for v1).
- Do not write any Dockerfile, k8s manifests, or Helm values in this spec — that is ENG-02.
- Never hard-code topic name, bootstrap servers, or schema registry URL anywhere in the implementation.
