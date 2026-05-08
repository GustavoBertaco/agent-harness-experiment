# Research: Kubernetes CDC Event Generator

**Phase**: 0 — Pre-design research  
**Branch**: `001-k8s-cdc-event-generator`  
**Date**: 2026-05-08

---

## 1. Kafka Producer Configuration

**Decision**: `batch.size=200000`, `linger.ms=100`, `compression.type=lz4`, `queue.buffering.max.messages=100000`, `acks=1`

**Rationale**: At 100–500 events/sec the bottleneck is not raw throughput but batching overhead. Increasing `batch.size` from the 16 KB default to 200 KB allows meaningful batching without memory pressure. `linger.ms=100` gives the producer time to fill batches before flushing, which is acceptable because CDC consumers tolerate ~100 ms event latency. LZ4 compression is near-zero CPU cost at this scale and reduces network bytes. `acks=1` is sufficient for synthetic data — leader acknowledgement prevents silent drops without paying the full ISR-sync penalty. `queue.buffering.max.messages=100000` caps in-process queue memory.

**Alternatives considered**:
- `acks=all`: Full ISR sync — unnecessary durability for synthetic test data; halves throughput.
- `batch.size=16384` (default): Causes tiny batches at 100 events/sec, defeating batching entirely.
- `compression.type=gzip`: Higher compression ratio but 10× CPU cost vs. LZ4; irrelevant gain for small payloads.

---

## 2. Avro Serialization Library

**Decision**: `fastavro` for all Avro serialization

**Rationale**: fastavro is 8–10× faster than the official `avro-python3` package (C extensions vs. pure-Python class hierarchy). API is straightforward: `fastavro.schemaless_writer` / `schemaless_reader` write/read bytes from an in-memory buffer. Actively maintained, widely used in production CDC pipelines.

**Alternatives considered**:
- `avro-python3` (official Apache): Pure Python, expensive property-access overhead; rejected on performance.
- `PyArrow`: Different use case (columnar analytics, not row-level CDC); overkill.

---

## 3. Debezium CDC Avro Envelope Schema

**Decision**: Use the minimal Debezium envelope with a dynamically generated `Row` record derived from `PAYLOAD_TEMPLATE`

**Envelope fields and Avro types**:

| Field         | Avro Type                          | Notes                                          |
|---------------|------------------------------------|------------------------------------------------|
| `op`          | `string`                           | `"c"`, `"u"`, `"d"`, `"r"`                    |
| `before`      | `["null", Row]`                    | `null` for `c`; populated for `u`/`d`          |
| `after`       | `["null", Row]`                    | `null` for `d`                                 |
| `source`      | Source record (see below)          | Synthetic connector metadata                   |
| `ts_ms`       | `long`                             | Epoch milliseconds at event generation         |
| `transaction` | `["null", "string"]`, default null | Omitted from default template (stub as null)   |

**Minimal Source record**:

| Field       | Avro Type | Synthetic value                          |
|-------------|-----------|------------------------------------------|
| `version`   | `string`  | `"1.9.7.Final"` (pinned constant)        |
| `connector` | `string`  | `"mysql"` (constant)                     |
| `name`      | `string`  | Value of `KAFKA_TOPIC`                   |
| `ts_ms`     | `long`    | Same as envelope `ts_ms`                 |
| `db`        | `string`  | `"synthetic_db"` (constant)              |
| `table`     | `string`  | `"events"` (constant)                    |
| `file`      | `string`  | Synthesized binlog filename              |
| `pos`       | `long`    | Monotonically increasing counter         |

Full MySQL connector source fields (`server_id`, `gtid`, `query`, etc.) are intentionally omitted — they carry no semantic value for a synthetic generator and add schema complexity with no downstream benefit.

**Alternatives considered**:
- Full Debezium MySQL source block: Adds `server_id`, `gtid`, `thread`, `query` — all null for synthetic data; bloats schema for zero gain.
- Custom non-Debezium envelope: Loses compatibility with Debezium-aware consumers.

---

## 4. Schema Registry Wire Format

**Decision**: Use `confluent_kafka.schema_registry.avro.AvroSerializer` in Schema Registry mode; use raw `fastavro.schemaless_writer` in raw mode

**Rationale**: In Schema Registry mode, `AvroSerializer` automatically prepends the 5-byte wire prefix (magic byte `0x00` + 4-byte big-endian schema ID) and registers the schema on first use. No manual wire format handling is needed. In raw mode (no `SCHEMA_REGISTRY_URL`), `fastavro.schemaless_writer` emits plain Avro bytes with no prefix — this is the default and requires no confluent Schema Registry dependency.

**Wire format** (SR mode): `[0x00][schema_id: 4 bytes big-endian][avro_payload]`

**Alternatives considered**:
- Manual wire prefix in raw mode: Unnecessary — raw mode consumers do not expect the prefix; adding it would break them.
- `confluent_kafka.avro.AvroProducer` (legacy): Deprecated; replaced by `AvroSerializer` + `SerializingProducer`.

---

## 5. Dynamic Avro Schema Generation

**Decision**: Build schema as a Python `dict` at runtime from `PAYLOAD_TEMPLATE`; convert to fastavro parsed schema via `fastavro.parse_schema(dict)`

**Rationale**: Avro schemas are JSON objects. Constructing them as dicts in Python is idiomatic and eliminates the need for `.avsc` files. `fastavro.parse_schema()` accepts a dict directly and returns a validated, indexed schema object ready for serialization. The `Row` record schema is derived by mapping PAYLOAD_TEMPLATE generator types to Avro types:

| Generator token   | Avro type  |
|-------------------|------------|
| `uuid`            | `string`   |
| `decimal(N)`      | `string`   |
| `choice(...)`     | `string`   |
| `timestamp`       | `long`     |
| `string(N)`       | `string`   |
| `int`             | `int`      |
| `int(min,max)`    | `int`      |

**Alternatives considered**:
- `dataclasses-avroschema`: Adds Pydantic/dataclass coupling; unnecessary abstraction.
- Static `.avsc` files: Cannot accommodate runtime PAYLOAD_TEMPLATE changes without rebuild.

---

## 6. Rate Limiting at 100 events/sec

**Decision**: Custom token bucket (~40 lines of Python) — no third-party rate-limit library

**Rationale**: At 100–500 events/sec, a simple token bucket is completely sufficient and avoids adding a dependency. The implementation: track `tokens` (float), `last_refill` (timestamp), `rate` (tokens/sec), `capacity` (tokens). On each `acquire()` call: refill tokens proportional to elapsed time, consume one token, sleep if tokens exhausted. This handles burst cleanly and produces accurate average throughput. A `time.sleep(1/rate)` loop is rejected because sleep granularity on Linux is ~1 ms, causing drift at high rates, and it cannot accumulate burst credit.

**Alternatives considered**:
- `pyrate-limiter`: Adds external dependency for functionality achievable in 40 lines.
- `time.sleep(1/rate)`: Sleep granularity drift accumulates; cannot absorb bursts; rejected.
- asyncio-based producer: Adds async complexity throughout the codebase; single-threaded sync is sufficient.
