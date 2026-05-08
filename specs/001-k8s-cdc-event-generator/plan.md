# Implementation Plan: Kubernetes CDC Event Generator

**Branch**: `001-k8s-cdc-event-generator` | **Date**: 2026-05-08 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/001-k8s-cdc-event-generator/spec.md`

## Summary

Deploy a Python-based synthetic CDC event producer to a local Kubernetes cluster that emits Debezium-compatible Avro events to Kafka at a configurable rate (default 100 events/sec), with dynamic schema generation from a ConfigMap-injected `PAYLOAD_TEMPLATE` and optional Schema Registry integration — all with zero cloud dependencies.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: `confluent-kafka-python` (Kafka producer + Schema Registry client), `fastavro` (Avro serialization), `pytest` (tests)  
**Storage**: N/A — Kafka is an external dependency managed via Helm; no persistent storage  
**Testing**: pytest with unit tests (mocked Kafka/SR) + integration tests (real Kafka via minikube)  
**Target Platform**: Kubernetes (local: minikube primary; kind and Docker Desktop Kubernetes as alternatives)  
**Project Type**: Containerized service (Kubernetes Deployment)  
**Performance Goals**: ≥ 100 events/sec per replica; pod ready → first event ≤ 60 sec; ≤ 5 retries before fatal exit  
**Constraints**: Plaintext Kafka only (no SASL/TLS); zero cloud or paid-service dependencies; safe replica range 1–5; `cpu: 100m` / `memory: 256Mi` per pod  
**Scale/Scope**: 1–5 replicas; ~100–500 events/sec aggregate; local developer machine only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

### Pre-research check (Phase 0 gate)

| Gate                   | Status | Evidence                                                                 |
|------------------------|--------|--------------------------------------------------------------------------|
| **Spec gate**          | ✅ PASS | `spec.md` exists; all 5 open questions resolved in Clarifications section; no `[OPEN]` markers remain |
| **TDD gate**           | ✅ PASS | FR-012 mandates tests-before-code; enforced in task ordering (tasks.md will place test tasks before implementation tasks) |
| **Isolation gate**     | ✅ PASS | All code targets `experiments/k8s-cdc-event-generator/`; K8s manifests go in `experiments/k8s-cdc-event-generator/k8s/` |
| **Security gate**      | ✅ PASS | Single-feature path (not a wave branch); security review runs at PR time only |

### Post-design re-check (Phase 1 gate)

| Gate               | Status | Notes                                                                                       |
|--------------------|--------|---------------------------------------------------------------------------------------------|
| **Spec gate**      | ✅ PASS | All requirements (FR-001–FR-015) traceable to design artifacts; no new open questions introduced |
| **TDD gate**       | ✅ PASS | All 5 entities in data-model.md have defined validation rules → directly testable contracts  |
| **Isolation gate** | ✅ PASS | Project structure below targets `experiments/k8s-cdc-event-generator/` exclusively            |
| **Security gate**  | ✅ PASS | Plaintext-only transport is by design (FR-013, Assumptions); no credentials in any artifact  |

**Violations requiring justification**: None.

## Project Structure

### Documentation (this feature)

```text
specs/001-k8s-cdc-event-generator/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output — technology decisions
├── data-model.md        # Phase 1 output — entities, validation rules, state machines
├── quickstart.md        # Phase 1 output — cold-start developer guide
├── contracts/           # Phase 1 output — Avro schema contracts
│   ├── avro-envelope.avsc  # Debezium CDC envelope Avro schema (default Row)
│   └── README.md           # Schema evolution policy and PAYLOAD_TEMPLATE reference
└── tasks.md             # Phase 2 output (/speckit-tasks command — NOT created here)
```

### Source Code

```text
experiments/k8s-cdc-event-generator/
├── producer/
│   ├── __init__.py
│   ├── config.py          # ProducerConfig: load + validate env vars; exits 1 on invalid config
│   ├── schema.py          # Avro schema builder from PAYLOAD_TEMPLATE; raw/SR serializer factory
│   ├── event_generator.py # Synthetic Row + CDC Event generation; OperationWeights sampling
│   ├── rate_limiter.py    # Token bucket rate limiter (custom, ~40 lines, no deps)
│   └── main.py            # Entry point: lifecycle orchestration, Kafka connect, produce loop
├── tests/
│   ├── unit/
│   │   ├── test_config.py          # ProducerConfig validation, env var parsing, OP_WEIGHTS
│   │   ├── test_schema.py          # PAYLOAD_TEMPLATE → Avro schema; token mapping; unknown tokens
│   │   ├── test_event_generator.py # Row generation; op sampling; before/after nullability rules
│   │   └── test_rate_limiter.py    # Token bucket: refill rate, burst, sleep trigger
│   └── integration/
│       └── test_producer_e2e.py    # Requires running Kafka; produces N messages, asserts receipt
├── k8s/
│   ├── configmap.yaml     # All producer env vars including default PAYLOAD_TEMPLATE
│   └── deployment.yaml    # Deployment with resource limits, ConfigMap envFrom, label selectors
├── Dockerfile             # python:3.11-slim base; non-root user; no dev deps in image
├── requirements.txt       # confluent-kafka, fastavro (pinned versions)
├── requirements-dev.txt   # pytest, pytest-mock, pytest-cov (dev only)
├── pytest.ini             # testpaths, markers (unit, integration), integration skip by default
└── README.md              # Prerequisites, install steps, run steps, scaling guidance, teardown
```

**Structure Decision**: Single project (Option 1) — the experiment is a standalone containerized service with no frontend or mobile component. Code lives in `experiments/k8s-cdc-event-generator/`; K8s manifests are co-located under `k8s/` within that directory for discoverability.

## Complexity Tracking

No constitution violations.

---

## Key Design Decisions

### Rate control
Token bucket (custom, ~40 lines). Tracks `tokens` (float), `last_refill` (timestamp), `rate` (tokens/sec), `capacity` (burst cap = 1 second of events). On each `acquire()`: refill tokens proportional to elapsed time, cap at capacity, consume one token, sleep if tokens exhausted. Simple `time.sleep(1/rate)` is rejected — sleep granularity drift accumulates at 100 Hz and it cannot accumulate burst credit.

### Avro schema generation
`PAYLOAD_TEMPLATE` is parsed at startup into a Python dict; the `Row` Avro record is built programmatically (field name → Avro type via generator token mapping); the full envelope dict is passed to `fastavro.parse_schema()`. No `.avsc` file is read at runtime — the `.avsc` in `contracts/` is the human-readable reference spec, not the runtime source.

### Serialization dual-mode
A factory function returns either a `RawSerializer` (wraps `fastavro.schemaless_writer`) or a `SchemaRegistrySerializer` (wraps `confluent_kafka.schema_registry.avro.AvroSerializer`) based on `SCHEMA_REGISTRY_URL`. The produce loop calls a single `serialize(event)` → `bytes` interface regardless of mode.

### Kafka producer config
`batch.size=200000`, `linger.ms=100`, `compression.type=lz4`, `acks=1`. Rationale in `research.md` §1. These are set as static producer config — not env-var-configurable (out of scope for M1; the spec does not require tunable producer internals).

### Before/after synthetic state
For `u`/`d` operations, `before` is a freshly generated synthetic Row (not the previous `after` value). This is intentional — tracking prior state across events would require in-memory state per logical record, adding complexity with no benefit for a synthetic generator. The spec acknowledges this: "it does not represent the actual prior state — it is synthetic."

### Kubernetes resources
`cpu: 100m` request = `100m` limit; `memory: 256Mi` request = `256Mi` limit (FR-015). Limits equal requests to ensure QoS class `Guaranteed`, preventing OOM eviction during brief memory spikes.
