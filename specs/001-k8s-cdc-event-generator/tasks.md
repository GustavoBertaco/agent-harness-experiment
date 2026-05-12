# Tasks: Kubernetes CDC Event Generator

**Input**: Design documents from `/specs/001-k8s-cdc-event-generator/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: TDD is mandatory (FR-012 + CLAUDE.md). Every implementation task is preceded by a failing-test task. Integration tests are gated by the `integration` pytest marker and skipped by default.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description — file path`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no incomplete dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup (Project Skeleton)

**Purpose**: Create directory structure, package init files, Docker image, pytest config, and pinned dependency files.

- [x] T001 Create experiment directory skeleton: `experiments/k8s-cdc-event-generator/producer/`, `tests/unit/`, `tests/integration/`, `k8s/`; add empty `__init__.py` to each Python package (`producer/`, `tests/unit/`, `tests/integration/`)
- [x] T002 [P] Create `experiments/k8s-cdc-event-generator/requirements.txt` with pinned `confluent-kafka` and `fastavro` (consult research.md §2 for version guidance)
- [x] T003 [P] Create `experiments/k8s-cdc-event-generator/requirements-dev.txt` with `pytest`, `pytest-mock`, `pytest-cov`
- [x] T004 [P] Create `experiments/k8s-cdc-event-generator/pytest.ini` with `testpaths = tests/unit tests/integration`, markers `unit` and `integration`, `addopts = -m "not integration"` (integration tests skipped by default)
- [x] T005 [P] Create `experiments/k8s-cdc-event-generator/Dockerfile` using `python:3.11-slim` base, non-root user `appuser (uid=1001)`, copies and installs only `requirements.txt` (no dev deps), `CMD ["python", "-m", "producer.main"]`

**Checkpoint**: Directory skeleton exists; all config files in place.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared core modules required by every user story — ProducerConfig, RateLimiter, and Avro schema builder. TDD: write failing tests first, then implement.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 [P] Write failing unit tests for `ProducerConfig` and `OperationWeights`: env var loading with defaults (`KAFKA_BOOTSTRAP_SERVERS=localhost:9092`, `KAFKA_TOPIC=cdc-events`, `EVENT_RATE_PER_SEC=100`, etc.), type coercion, range validation (`event_rate` in 1–10 000), `OP_WEIGHTS` format parsing (`c:70,u:20,d:10`), weights-sum-to-100 validation (±0.001 tolerance), `SystemExit(1)` on any invalid field or unrecognized token in `experiments/k8s-cdc-event-generator/tests/unit/test_config.py`
- [x] T007 [P] Write failing unit tests for `RateLimiter` token bucket: refill proportional to elapsed time, burst capacity capped at 1 second of events, `acquire()` sleeps when tokens exhausted, average achieved rate stays within 5% of target over a 1-second window in `experiments/k8s-cdc-event-generator/tests/unit/test_rate_limiter.py`
- [x] T008 [P] Write failing unit tests for Avro schema builder: `PAYLOAD_TEMPLATE` JSON string → `Row` Avro record dict (`name="Row"`, `namespace="synthetic.cdc"`), all 7 generator token mappings (`uuid`→`string`, `timestamp`→`long`, `decimal(N)`→`string`, `choice(...)`→`string`, `string(N)`→`string`, `int`→`int`, `int(min,max)`→`int`), unknown token raises `SystemExit(1)`, field names with invalid Avro identifiers raise `SystemExit(1)`, built schema dict passes `fastavro.parse_schema()` without error in `experiments/k8s-cdc-event-generator/tests/unit/test_schema.py`
- [x] T009 [P] Implement `ProducerConfig` (dataclass, loads from `os.environ`, all fields immutable after init) and `OperationWeights` (parsed from `op_weights` string, exposed as normalized floats for `random.choices`) in `experiments/k8s-cdc-event-generator/producer/config.py` to pass T006
- [x] T010 [P] Implement `RateLimiter` token bucket (~40 lines): `__init__(rate)`, `acquire()` refills tokens by `elapsed × rate`, caps at `rate` (1-second burst), sleeps `deficit / rate` when empty in `experiments/k8s-cdc-event-generator/producer/rate_limiter.py` to pass T007
- [x] T011 [P] Implement `build_row_schema(payload_template_json: str) -> dict` and `build_envelope_schema(payload_template_json: str) -> parsed_schema` in `experiments/k8s-cdc-event-generator/producer/schema.py`; envelope wraps `Row` in the Debezium fields (`before`, `after`, `source`, `op`, `ts_ms`, `transaction`) per `contracts/avro-envelope.avsc`; call `fastavro.parse_schema()` and return the result to pass T008

**Checkpoint**: Foundation ready — `ProducerConfig`, `RateLimiter`, and Avro schema builder are all implemented and tested.

---

## Phase 3: User Story 1 — Cold-Start Event Production (Priority: P1) 🎯 MVP

**Goal**: Developer clones the repo, applies the Kubernetes manifests against a local minikube cluster, and sees ≥100 CDC events/sec on the `cdc-events` Kafka topic within 60 seconds of pod readiness — zero cloud dependencies, zero image rebuild.

**Independent Test**: `kubectl apply -f k8s/`; run a Kafka consumer; assert ≥100 messages received within 10 seconds of pod reaching Running state.

- [x] T012 [US1] Write failing unit tests for `Row` generation: each generator token type (`uuid`, `timestamp`, `decimal(N)`, `choice(...)`, `string(N)`, `int`, `int(min,max)`) produces a value matching the expected Python type and format, field count matches `PAYLOAD_TEMPLATE`, all field names are valid Avro identifiers in `experiments/k8s-cdc-event-generator/tests/unit/test_event_generator.py`
- [x] T013 [US1] Write failing unit tests for `Source` record: `version="1.9.7.Final"`, `connector="mysql"`, `db="synthetic_db"`, `table="events"`, `file="binlog.000001"`, `name` matches `KAFKA_TOPIC`, `pos` is non-negative and strictly increasing across successive calls, `ts_ms` within ±5 000 ms of `time.time() * 1000` in `experiments/k8s-cdc-event-generator/tests/unit/test_event_generator.py`
- [x] T014 [US1] Write failing unit tests for CDC Event `before`/`after` nullability: `op="c"` → `before=null, after=Row`; `op="u"` → `before=Row, after=Row`; `op="d"` → `before=Row, after=null`; `op="r"` → `before=null, after=Row`; and for `OperationWeights` sampling: default c:70/u:20/d:10 distribution verified over 10 000 samples (within ±3%), and weights-sum-to-100 validation in `experiments/k8s-cdc-event-generator/tests/unit/test_event_generator.py`
- [x] T015 [US1] Implement `event_generator.py`: `generate_row(schema_fields, payload_template)` → dict, `generate_source(topic, pos)` → dict, `generate_event(op, row_schema, source_pos, ts_ms)` → dict with correct `before`/`after` per op, `OperationWeights.sample()` using `random.choices` with normalized weights in `experiments/k8s-cdc-event-generator/producer/event_generator.py` to pass T012–T014
- [x] T016 [US1] Write failing unit tests for `RawSerializer`: `serialize(event_dict, schema)` returns `bytes`, output has no 5-byte Confluent wire prefix (first byte ≠ `0x00`), output is valid Avro decodable with `fastavro.schemaless_reader` using the same schema in `experiments/k8s-cdc-event-generator/tests/unit/test_schema.py`
- [x] T017 [US1] Implement `RawSerializer` (wraps `fastavro.schemaless_writer` into a `BytesIO` buffer and returns `.getvalue()`) and serializer factory `make_serializer(config, schema) -> Serializer` (returns `RawSerializer` when `config.schema_registry_url` is empty) in `experiments/k8s-cdc-event-generator/producer/schema.py` to pass T016
- [x] T018 [US1] Write failing unit tests for producer lifecycle in `experiments/k8s-cdc-event-generator/tests/unit/test_main.py`: (a) Kafka connect with exponential backoff — mock `confluent_kafka.Producer` to raise `KafkaException` 5× then verify `SystemExit(1)` and 5 retry log lines; (b) startup log contains config summary (bootstrap servers, topic, rate, mode); (c) per-batch log contains `rate=<n>/s`; (d) rate-drift warning logged when achieved rate < 90% of target
- [x] T019 [US1] Implement `producer/main.py`: load `ProducerConfig`, build envelope schema, call `make_serializer`, connect to Kafka with exponential backoff (delays: 1s, 2s, 4s, 8s, 16s, exit-1 after 5 failures), run produce loop (`generate_event` → `serialize` → `producer.produce` → `RateLimiter.acquire`), emit startup summary log, per-batch rate log, rate-drift warning (achieved < 90% target), handle `SIGTERM`/`SIGINT` gracefully in `experiments/k8s-cdc-event-generator/producer/main.py` to pass T018
- [x] T020 [US1] Write failing integration test (marker: `integration`): build producer Docker image against minikube, apply `k8s/` manifests, wait for pod Running, run Kafka consumer, assert ≥100 messages received on `cdc-events` topic within 10 seconds in `experiments/k8s-cdc-event-generator/tests/integration/test_producer_e2e.py`
- [x] T021 [P] [US1] Create `experiments/k8s-cdc-event-generator/k8s/configmap.yaml`: `ConfigMap` named `event-generator-config`, label `app=event-generator`, all env vars (`KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC`, `EVENT_RATE_PER_SEC`, `SCHEMA_REGISTRY_URL`, `OP_WEIGHTS`) with defaults per spec, and `PAYLOAD_TEMPLATE` set to the default JSON from data-model.md §2
- [x] T022 [P] [US1] Create `experiments/k8s-cdc-event-generator/k8s/deployment.yaml`: `Deployment` named `event-generator`, label `app=event-generator` on Deployment, pod template, and selector, 1 replica, `image: cdc-event-generator:latest`, `imagePullPolicy: Never` (minikube), `envFrom: configMapRef: event-generator-config`, resource requests and limits `cpu: 100m` / `memory: 256Mi`

**Checkpoint**: User Story 1 fully functional — cold-start walkthrough produces events in local Kubernetes.

---

## Phase 4: User Story 2 — Configurable Event Rate and Schema (Priority: P2)

**Goal**: Developer sets `SCHEMA_REGISTRY_URL` in the ConfigMap and restarts the pod; producer registers the Avro schema under `cdc-events-value`, switches to Confluent wire format, and logs SR mode on startup — no image rebuild required.

**Independent Test**: Set `SCHEMA_REGISTRY_URL` in ConfigMap, delete pod; confirm startup log shows `mode=schema-registry`, schema appears under `<topic>-value` subject, and messages carry the 5-byte wire prefix.

- [x] T023 [US2] Write failing unit tests for `SchemaRegistrySerializer`: schema registration called once in `__init__` (mock `SchemaRegistryClient`), `serialize(event, schema)` output starts with magic byte `\x00` followed by 4-byte big-endian schema ID, `SystemExit(1)` raised with clear log message when SR client raises `SchemaRegistryError` at init in `experiments/k8s-cdc-event-generator/tests/unit/test_schema.py`
- [x] T024 [US2] Implement `SchemaRegistrySerializer` using `confluent_kafka.schema_registry.SchemaRegistryClient` for registration and `confluent_kafka.schema_registry.avro.AvroSerializer` for serialization; register schema under `<topic>-value` subject in `__init__`; exit-1 on registry unreachable in `experiments/k8s-cdc-event-generator/producer/schema.py` to pass T023
- [x] T025 [US2] Write failing unit tests for updated serializer factory: `make_serializer(config, schema)` returns `SchemaRegistrySerializer` when `config.schema_registry_url` is non-empty, returns `RawSerializer` when empty, both cases return objects with a `serialize(event, schema) -> bytes` interface in `experiments/k8s-cdc-event-generator/tests/unit/test_schema.py`
- [x] T026 [US2] Update `make_serializer` in `experiments/k8s-cdc-event-generator/producer/schema.py` to instantiate `SchemaRegistrySerializer` when `schema_registry_url` is non-empty, to pass T025
- [x] T027 [US2] Write failing unit tests for startup log content in `experiments/k8s-cdc-event-generator/tests/unit/test_main.py`: startup log line includes `rate=<n>/s`, `mode=raw` when SR URL empty, `mode=schema-registry url=<url>` when SR URL set
- [x] T028 [US2] Update startup log in `experiments/k8s-cdc-event-generator/producer/main.py` to emit `rate`, `mode`, and (if SR) `schema_registry_url` in the config summary log line to pass T027

**Checkpoint**: User Story 2 complete — SR mode and rate configurability both validated by tests.

---

## Phase 5: User Story 3 — Horizontal Scaling (Priority: P3)

**Goal**: `kubectl scale deployment event-generator --replicas=3` produces ≥270 events/sec total (≥N×90 tolerance); each pod independently logs its own per-batch `rate=` metric.

**Independent Test**: Scale to 3 replicas, consume topic for 10 seconds, assert total message count ≥270.

- [x] T029 [US3] Write failing integration test (marker: `integration`): scale Deployment to 3 replicas, start Kafka consumer, count messages over 10 seconds, assert count ≥270 (3 replicas × 90 events/sec × 10 sec) in `experiments/k8s-cdc-event-generator/tests/integration/test_producer_e2e.py`
- [x] T030 [P] [US3] Add scaling verification section to `experiments/k8s-cdc-event-generator/README.md`: `kubectl scale` command, per-pod log check command (`kubectl logs -l app=event-generator --prefix=true | grep "rate="`), explanation that total throughput = replicas × rate

**Checkpoint**: User Story 3 complete — horizontal scaling yields proportional throughput with per-pod log verification.

---

## Phase 6: User Story 4 — Clean Teardown (Priority: P4)

**Goal**: `kubectl delete -f k8s/` removes all producer-owned resources; `kubectl get all -l app=event-generator` returns empty; Kafka and Schema Registry are unaffected.

**Independent Test**: Apply manifests, then delete them; query all resources with `app=event-generator` label and assert empty result.

- [x] T031 [US4] Write failing integration test (marker: `integration`): apply `k8s/` manifests, wait for pod Running, delete `k8s/` manifests, poll `kubectl get all -l app=event-generator --no-headers` for up to 30 seconds and assert empty output in `experiments/k8s-cdc-event-generator/tests/integration/test_producer_e2e.py`
- [x] T032 [US4] Audit `k8s/configmap.yaml` and `k8s/deployment.yaml`: confirm every resource (Deployment, pod template, ConfigMap) declares `app=event-generator` label; add teardown section to `experiments/k8s-cdc-event-generator/README.md` with `kubectl delete -f k8s/` and verification command

**Checkpoint**: All 4 user stories complete and independently testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all stories.

- [x] T033 [P] Run complete unit test suite (`pytest tests/unit -v`) in `experiments/k8s-cdc-event-generator/` and fix any failing tests
- [x] T034 [P] Validate README.md against quickstart.md step-by-step (diff the two documents) and update `experiments/k8s-cdc-event-generator/README.md` if any prerequisite, command, or step is missing or incorrect
- [x] T035 Validate that `contracts/avro-envelope.avsc` matches the schema produced at runtime by the schema builder: generate a live event with default `PAYLOAD_TEMPLATE`, decode it using the `.avsc` file as the reader schema via `fastavro`, and assert no exception is raised in `experiments/k8s-cdc-event-generator/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 completion; T006, T007, T008 can start in parallel; T009 depends on T006, T010 depends on T007, T011 depends on T008
- **Phase 3 (US1)**: Depends on Phase 2 completion; T014 depends on T012–T014; T015 before T017; T017 before T019; T020–T021 before T019 (manifests must exist for integration test)
- **Phase 4 (US2)**: Depends on Phase 3 (US1 complete); T024 depends on T023; T026 depends on T025; T028 depends on T027
- **Phase 5 (US3)**: Depends on Phase 3 (US1 complete); does NOT depend on Phase 4
- **Phase 6 (US4)**: Depends on Phase 3 (US1 complete); does NOT depend on Phases 4–5
- **Phase 7 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no other story dependencies
- **US2 (P2)**: Depends on US1 (serializer factory and main.py must exist)
- **US3 (P3)**: Depends on US1 (Deployment and main.py must exist); independent of US2
- **US4 (P4)**: Depends on US1 (manifests must exist); independent of US2–US3

### Within Each User Story (TDD order)

1. Write failing test (confirm it fails with `pytest`)
2. Write minimum implementation to pass it
3. Refactor if needed
4. Story complete when all tests pass and integration test validates independently

---

## Parallel Execution Examples

### Phase 2: Write all 3 test files simultaneously

```bash
# Round 1 — write failing tests (parallel):
Task: T006 — Write test_config.py
Task: T007 — Write test_rate_limiter.py
Task: T008 — Write test_schema.py (schema builder section)

# Confirm all fail: pytest tests/unit -v --co  # collect only

# Round 2 — implement to pass (parallel):
Task: T009 — Implement config.py
Task: T010 — Implement rate_limiter.py
Task: T011 — Implement schema.py (schema builder)
```

### Phase 3 (US1): Parallel manifest creation

```bash
# T021 and T022 write to different files:
Task: T021 — Create k8s/configmap.yaml
Task: T022 — Create k8s/deployment.yaml
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL** — blocks all stories)
3. Complete Phase 3: User Story 1 (T012–T022)
4. **STOP and VALIDATE**: `kubectl apply -f k8s/` → consumer reads ≥100 messages in 10s
5. Demo and confirm cold-start success

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready
2. Phase 3 (US1) → Cold-start events flowing (MVP!)
3. Phase 4 (US2) → Schema Registry and rate config working
4. Phase 5 (US3) → Horizontal scaling validated
5. Phase 6 (US4) → Clean teardown verified
6. Phase 7 → Polish pass

---

## Task Summary

| Phase | Tasks | Story | Count |
|-------|-------|-------|-------|
| Phase 1 | T001–T005 | Setup | 5 |
| Phase 2 | T006–T011 | Foundational | 6 |
| Phase 3 | T012–T022 | US1 (P1) | 11 |
| Phase 4 | T023–T028 | US2 (P2) | 6 |
| Phase 5 | T029–T030 | US3 (P3) | 2 |
| Phase 6 | T031–T032 | US4 (P4) | 2 |
| Phase 7 | T033–T035 | Polish | 3 |
| **Total** | | | **35** |

**Parallel opportunities**: 14 tasks marked [P] across all phases  
**MVP scope**: Phases 1–3 (22 tasks, US1 only)  
**Independent test criteria per story**:
- US1: ≥100 messages on `cdc-events` within 10s of pod readiness
- US2: SR mode startup log + schema under `<topic>-value` + wire-format messages
- US3: ≥270 messages over 10s with 3 replicas (3×90 tolerance)
- US4: `kubectl get all -l app=event-generator` empty after delete
