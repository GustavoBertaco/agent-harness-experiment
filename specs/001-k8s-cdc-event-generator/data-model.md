# Data Model: Kubernetes CDC Event Generator

**Phase**: 1 — Design  
**Branch**: `001-k8s-cdc-event-generator`  
**Date**: 2026-05-08

---

## Entities

### 1. CDC Event (Avro record — the wire payload)

The envelope emitted to Kafka on every produce cycle. Conforms to the Debezium CDC Avro envelope schema.

| Field         | Type              | Nullable | Description                                                                 |
|---------------|-------------------|----------|-----------------------------------------------------------------------------|
| `op`          | `string`          | No       | Operation type: `"c"` (create), `"u"` (update), `"d"` (delete), `"r"` (read/snapshot). Sampled by OP_WEIGHTS. |
| `before`      | `Row` \| `null`   | Yes      | Prior row state. `null` for `c` operations; populated for `u`/`d`.         |
| `after`       | `Row` \| `null`   | Yes      | New row state. `null` for `d` operations; populated for `c`/`u`.           |
| `source`      | `Source`          | No       | Synthetic connector metadata (see Source entity below).                     |
| `ts_ms`       | `long`            | No       | Event generation timestamp in epoch milliseconds.                           |
| `transaction` | `string` \| `null`| Yes      | Always `null` in M1 (transaction tracking out of scope).                    |

**Validation rules**:
- If `op == "c"`: `before` MUST be `null`, `after` MUST be non-null.
- If `op == "d"`: `before` MUST be non-null, `after` MUST be `null`.
- If `op == "u"`: `before` MUST be non-null, `after` MUST be non-null.
- If `op == "r"`: `before` MUST be `null`, `after` MUST be non-null (snapshot read).
- `ts_ms` MUST be within ±5 seconds of wall clock time.

---

### 2. Row (dynamically generated Avro record)

The data payload inside `before`/`after`. Schema is derived at startup from `PAYLOAD_TEMPLATE`.

**Default PAYLOAD_TEMPLATE** (shipped in ConfigMap):
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

**Generator token → Avro type mapping**:

| Token pattern  | Avro type | Example output           |
|----------------|-----------|--------------------------|
| `uuid`         | `string`  | `"a1b2c3d4-..."`         |
| `timestamp`    | `long`    | `1746700800000`          |
| `decimal(N)`   | `string`  | `"1234.56"` (N=2)        |
| `choice(a,b)`  | `string`  | `"active"` or `"inactive"` |
| `string(N)`    | `string`  | Random alphanumeric, len=N |
| `int`          | `int`     | `42`                     |
| `int(min,max)` | `int`     | Random in `[min, max]`   |

**Validation rules**:
- Row schema MUST be derived from `PAYLOAD_TEMPLATE` at startup; never hard-coded.
- All field names MUST be valid Avro identifiers (letters, digits, underscores; no leading digits).
- All token strings MUST match one of the defined generator patterns; unknown tokens are a fatal startup error.
- The resulting Avro record name is `Row`; the namespace is `synthetic.cdc`.

---

### 3. Source (Avro record — embedded in CDC Event)

Synthetic connector metadata injected into every CDC Event.

| Field       | Avro Type | Value                                             |
|-------------|-----------|---------------------------------------------------|
| `version`   | `string`  | `"1.9.7.Final"` (constant)                       |
| `connector` | `string`  | `"mysql"` (constant)                             |
| `name`      | `string`  | Value of `KAFKA_TOPIC` env var                    |
| `ts_ms`     | `long`    | Same as envelope `ts_ms`                         |
| `db`        | `string`  | `"synthetic_db"` (constant)                      |
| `table`     | `string`  | `"events"` (constant)                            |
| `file`      | `string`  | `"binlog.000001"` (constant)                     |
| `pos`       | `long`    | Monotonically increasing counter per replica pod  |

**Validation rules**:
- `pos` MUST be non-negative and strictly increasing within a single replica's lifetime.
- `name` MUST match the value of `KAFKA_TOPIC` to allow source-based topic routing.

---

### 4. ProducerConfig (runtime configuration object)

Loaded once at startup from environment variables. Immutable after initialization.

| Field                | Env Var                  | Default        | Type    | Validation                                             |
|----------------------|--------------------------|----------------|---------|--------------------------------------------------------|
| `bootstrap_servers`  | `KAFKA_BOOTSTRAP_SERVERS`| `localhost:9092`| `string`| Non-empty; must be reachable (connection attempt on startup) |
| `topic`              | `KAFKA_TOPIC`            | `cdc-events`   | `string`| Non-empty; valid Kafka topic name                      |
| `event_rate`         | `EVENT_RATE_PER_SEC`     | `100`          | `int`   | 1–10000 inclusive                                      |
| `schema_registry_url`| `SCHEMA_REGISTRY_URL`    | `""` (disabled)| `string`| If non-empty, must be a valid URL                      |
| `payload_template`   | `PAYLOAD_TEMPLATE`       | (default above)| `string`| Must be valid JSON; all tokens must be recognized      |
| `op_weights`         | `OP_WEIGHTS`             | `c:70,u:20,d:10`| `string`| Format `op:weight,...`; weights must sum to 100        |

**State transitions**:
- Config is loaded → validated → frozen. No runtime mutation.
- If any validation fails, the process exits with code 1 and logs the invalid field and value.

---

### 5. OperationWeights (parsed from OP_WEIGHTS)

Controls the probability distribution of CDC operation types.

| Field  | Type    | Default | Constraints                         |
|--------|---------|---------|-------------------------------------|
| `c`    | `float` | 70.0    | 0 ≤ value ≤ 100                    |
| `u`    | `float` | 20.0    | 0 ≤ value ≤ 100                    |
| `d`    | `float` | 10.0    | 0 ≤ value ≤ 100                    |

**Validation rules**:
- All three weights MUST be present.
- `c + u + d` MUST equal 100 (±0.001 floating-point tolerance).
- Weights are normalized to a probability distribution used in `random.choices()`.

---

## State Transitions

### ProducerLifecycle

```
STARTING
  ↓ (load and validate config)
CONFIG_LOADED
  ↓ (parse PAYLOAD_TEMPLATE → build Avro schema)
SCHEMA_READY
  ↓ (if SCHEMA_REGISTRY_URL set: register schema; if unreachable → EXIT_1)
  ↓ (connect to Kafka; if unavailable: retry ×5 → EXIT_1)
RUNNING
  ↓ (per-batch: generate events, produce, sleep)
  ↓ (rate drift detected → log WARNING, continue)
  ↓ (unrecoverable error → EXIT_1)
STOPPED (SIGTERM / SIGINT)
```

### CDC Event `before`/`after` state machine

```
op = "c": before=null,    after=Row(new)
op = "u": before=Row(old), after=Row(new)
op = "d": before=Row(old), after=null
op = "r": before=null,    after=Row(snap)
```

For `u`/`d`, the `before` row is generated as an independent synthetic record (different `uuid`, same schema shape). It does not represent the actual prior state — it is synthetic.
