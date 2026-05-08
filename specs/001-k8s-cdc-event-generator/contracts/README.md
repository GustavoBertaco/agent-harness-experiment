# Contracts: Kubernetes CDC Event Generator

This directory contains the interface contracts for the synthetic CDC event producer.

---

## `avro-envelope.avsc`

The Debezium-compatible Avro envelope schema emitted to Kafka for every CDC event.

**Important**: The `Row` record definition in this file reflects the **default** `PAYLOAD_TEMPLATE`. At runtime, the producer generates the `Row` schema dynamically from the `PAYLOAD_TEMPLATE` environment variable/ConfigMap entry. Changing `PAYLOAD_TEMPLATE` changes the `Row` schema without rebuilding the image.

### Schema modes

| Mode         | Condition                     | Serialization                                                          |
|--------------|-------------------------------|------------------------------------------------------------------------|
| **Raw Avro** | `SCHEMA_REGISTRY_URL` unset   | `fastavro.schemaless_writer` — plain Avro bytes, no wire prefix        |
| **SR mode**  | `SCHEMA_REGISTRY_URL` non-empty | confluent `AvroSerializer` — magic byte `0x00` + 4-byte schema ID + Avro bytes |

In SR mode the schema is registered under subject `<KAFKA_TOPIC>-value` on startup. If the registry is unreachable, the producer exits with code 1.

### Operation type semantics

| `op` | `before` | `after` | Weight (default) |
|------|----------|---------|-----------------|
| `c`  | `null`   | Row     | 70%             |
| `u`  | Row      | Row     | 20%             |
| `d`  | Row      | `null`  | 10%             |
| `r`  | `null`   | Row     | 0% (unused in M1) |

Weights are configurable via `OP_WEIGHTS` env var (e.g., `c:70,u:20,d:10`). Must sum to 100.

### Schema evolution policy

The envelope schema is a shared contract for all downstream streaming experiments in this harness. **Breaking changes require a new product spec**. Additive changes (new nullable fields with defaults) are non-breaking and require an ADR.

---

## PAYLOAD_TEMPLATE generator tokens

The `PAYLOAD_TEMPLATE` JSON value defines the Row schema fields and their value-generation strategy.

| Token           | Avro type | Description                                      |
|-----------------|-----------|--------------------------------------------------|
| `uuid`          | `string`  | UUID v4                                          |
| `timestamp`     | `long`    | Current epoch milliseconds                       |
| `decimal(N)`    | `string`  | Random decimal with N decimal places             |
| `choice(a,b,c)` | `string`  | Random choice from the provided list             |
| `string(N)`     | `string`  | Random alphanumeric string of length N           |
| `int`           | `int`     | Random integer (0–9999)                          |
| `int(min,max)`  | `int`     | Random integer in [min, max]                     |

Unknown tokens are a fatal startup error (exit code 1).

**Default template** (shipped in ConfigMap):
```json
{
  "id": "uuid",
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "status": "choice(active,inactive,pending)",
  "amount": "decimal(2)",
  "description": "string(32)"
}
```
