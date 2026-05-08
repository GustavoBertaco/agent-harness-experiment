# Feature Specification: Kubernetes CDC Event Generator

**Feature Branch**: `001-k8s-cdc-event-generator`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "Kubernetes-deployed synthetic CDC event generator that publishes Debezium Avro events to Kafka (see PS-001)"

## Clarifications

### Session 2026-05-08

- Q: What programming language should the producer be implemented in? → A: Python (confluent-kafka-python, pytest)
- Q: What fields make up the synthetic `after` row payload in the CDC event? → A: PAYLOAD_TEMPLATE-driven (JSON in ConfigMap); implementation must ship a sensible default template out-of-the-box so developers get working events without authoring one; template is changeable without rebuilding the image
- Q: Should the producer support Kafka authentication (SASL/TLS)? → A: Plaintext only, no auth; matches default local Helm Kafka; auth support is out of scope for M1
- Q: How should CDC operation types (c/u/d/r) be distributed across generated events? → A: Weighted random with configurable distribution; default c:70%, u:20%, d:10%; overridable via `OP_WEIGHTS` env var (e.g., `c:70,u:20,d:10`); `before` field is null for `c`, populated for `u`/`d`
- Q: Should the Kubernetes manifest include CPU/memory resource requests and limits? → A: Yes — both requests and limits; `cpu: 100m, memory: 256Mi` per pod; backs the documented safe replica range of 1–5

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cold-Start Event Production (Priority: P1)

A developer clones the repo, follows the README prerequisites, deploys the producer to a local Kubernetes cluster, and within minutes sees synthetic CDC events flowing on a Kafka topic — with zero cloud dependencies and no prior Kubernetes expertise required.

**Why this priority**: This is the foundational capability. Without it, no downstream streaming experiment can run. It is also the hardest path to get right (cold machine, docs-only onboarding), so validating it end-to-end first eliminates the largest risk.

**Independent Test**: Deploy the producer via the documented manifest apply command on a fresh minikube cluster and confirm ≥ 100 messages appear on the Kafka topic within 10 seconds of pod readiness.

**Acceptance Scenarios**:

1. **Given** a fresh local Kubernetes cluster and Kafka running via Helm, **When** the developer runs the manifest apply command, **Then** the producer pod reaches Running state and events begin flowing to the configured topic within 60 seconds.
2. **Given** the producer is running at default configuration (100 events/sec), **When** a Kafka consumer connects to the topic, **Then** ≥ 100 messages are received within 10 seconds.
3. **Given** the README prerequisites are installed, **When** a developer follows the documented steps from a cold clone, **Then** events are flowing within 30 minutes and no step requires cloud access or paid subscriptions.

---

### User Story 2 — Configurable Event Rate and Schema (Priority: P2)

A developer adjusts the event rate, topic name, and Avro schema mode via environment variables or ConfigMap — without rebuilding the container image — and the producer immediately respects the new configuration on next pod start.

**Why this priority**: Configurability is what makes this service reusable across experiments. Different experiments may need different rates or topic names; the Schema Registry toggle allows experiments to opt in to schema validation without forcing it on everyone.

**Independent Test**: Change `EVENT_RATE_PER_SEC` in the ConfigMap, delete the pod to force a restart, and confirm the new rate is reflected in the producer logs and message throughput.

**Acceptance Scenarios**:

1. **Given** the producer is deployed with `EVENT_RATE_PER_SEC=200`, **When** the pod starts, **Then** ≥ 200 messages/sec are produced and the startup log reflects the configured rate.
2. **Given** `SCHEMA_REGISTRY_URL` is set to a running local registry, **When** the pod starts, **Then** the Avro schema is registered under `<topic>-value` and events use the Schema Registry wire format (magic byte + schema ID prefix).
3. **Given** `SCHEMA_REGISTRY_URL` is unset or empty, **When** the pod starts, **Then** the producer emits raw Avro bytes with no Schema Registry dependency and the startup log confirms raw mode.

---

### User Story 3 — Horizontal Scaling (Priority: P3)

A developer scales the producer Deployment to multiple replicas and observes proportional throughput increase, with each replica independently logging its own rate.

**Why this priority**: Scaling is required to test downstream consumers under higher load. It comes after basic production is proven because it builds on a working single-replica deployment.

**Independent Test**: Scale to 3 replicas, count messages over 10 seconds, and assert the total is ≥ 3 × configured rate × 10 × 0.9 (10% tolerance).

**Acceptance Scenarios**:

1. **Given** the producer is running at 1 replica (100 events/sec), **When** the developer scales to 3 replicas, **Then** total message throughput increases to ≥ 270 events/sec within 10 seconds.
2. **Given** 3 replicas are running, **When** the developer checks logs for each pod, **Then** each pod logs its own per-batch status line with its replica-local rate.

---

### User Story 4 — Clean Teardown (Priority: P4)

A developer removes the producer by deleting its manifests and all producer-owned Kubernetes resources are gone — no orphaned pods, ConfigMaps, or Services remain. Kafka and Schema Registry (managed via Helm) are unaffected.

**Why this priority**: Clean teardown is required for repeatability of experiments. Without it, leftover resources can interfere with re-deployments or consume cluster resources.

**Independent Test**: Run the manifest delete command and query Kubernetes for all resources with the producer's label; assert the result is empty.

**Acceptance Scenarios**:

1. **Given** the producer Deployment and ConfigMap are deployed, **When** the developer runs the manifest delete command, **Then** all producer-owned resources are removed and `kubectl get all -l app=event-generator` returns empty.
2. **Given** the producer is deleted, **When** the developer queries Kafka, **Then** the Kafka cluster and topics remain intact (only the producer is gone).

---

### Edge Cases

- **Schema Registry unreachable at startup**: Producer must exit with code 1 and log a clear error; Kubernetes restarts the pod with visible restart count and reason in `kubectl describe pod`.
- **Kafka broker unavailable**: Producer must retry with exponential backoff (max 5 retries), log each retry attempt, and exit with code 1 after exhausting retries.
- **Event rate drift under load**: Producer logs a warning when achieved rate falls below target rate; it does not crash or exit — it keeps running.
- **Pod crashes silently**: Producer must always emit at least one startup log line and one per-batch status line so `kubectl logs` always reflects the last known state.
- **Replica count floods local machine**: README must document safe default replica range (1–5) and explain that total throughput = replicas × rate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST deploy to a local Kubernetes cluster via a single manifest apply command and begin producing events within 60 seconds of pod readiness.
- **FR-002**: System MUST emit synthetic CDC events to a configurable Kafka topic at a configurable rate (default: 100 events/sec).
- **FR-003**: System MUST serialize all events using the Debezium CDC Avro envelope schema (`op`, `before`, `after`, `ts_ms`, `source` fields). Operation types are sampled by weighted random distribution (default `c:70%, u:20%, d:10%`, configurable via `OP_WEIGHTS`); `before` MUST be `null` for `c` operations and populated with a prior synthetic row state for `u`/`d` operations.
- **FR-004**: System MUST support raw Avro mode (default): serializes events as raw Avro bytes with no Schema Registry dependency.
- **FR-005**: System MUST support Schema Registry mode: when `SCHEMA_REGISTRY_URL` is set, registers the schema on startup and uses the wire format (magic byte + schema ID prefix) for all messages.
- **FR-006**: System MUST be fully configurable via Kubernetes ConfigMap and environment variables: at minimum `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC`, `EVENT_RATE_PER_SEC`, `SCHEMA_REGISTRY_URL`, `PAYLOAD_TEMPLATE`, and `OP_WEIGHTS`. `PAYLOAD_TEMPLATE` is a JSON string defining the synthetic `after` row fields and their value-generation strategy (e.g., `{"id": "uuid", "amount": "decimal(2)", "status": "choice(active,inactive)"}`); the shipped ConfigMap manifest MUST include a working default so no developer configuration is required on first deploy. Changing `PAYLOAD_TEMPLATE` without rebuilding the image MUST be supported; incompatible schema changes with a live Schema Registry are out of scope for M1.
- **FR-007**: System MUST scale horizontally: N replicas must each independently produce at the configured rate, yielding approximately N × rate total throughput.
- **FR-008**: System MUST emit structured log lines at startup (configuration summary), per-batch (achieved rate), on rate drift (warning), and on error — never run silently.
- **FR-009**: System MUST exit with code 1 and log a clear error message when Schema Registry is configured but unreachable at startup.
- **FR-010**: System MUST retry connection to Kafka with exponential backoff on startup failure (max 5 retries) before exiting with code 1.
- **FR-011**: Deleting the producer manifests MUST remove all producer-owned Kubernetes resources; no pods, ConfigMaps, or Services with the producer's label may remain.
- **FR-015**: The producer Deployment manifest MUST declare resource requests and limits of `cpu: 100m` and `memory: 256Mi` per container to ensure predictable scheduling within the safe replica range of 1–5.
- **FR-012**: All producer behavior MUST be covered by automated tests written before implementation code, following TDD (failing test first, minimum code to pass, then refactor).
- **FR-013**: System MUST operate with zero cloud or external subscription dependencies under any configuration path.
- **FR-014**: System MUST include a README inside the experiment directory documenting prerequisites, install steps, run steps, safe replica limits, and a cold-start walkthrough.

### Key Entities

- **CDC Event**: A synthetic record conforming to the Debezium CDC Avro envelope — contains operation type (`c`/`u`/`d`/`r`), optional before/after row state, event timestamp, and source metadata (db, table, topic name). All field values are synthetic; no real data or PII. Operation types are sampled using a weighted random distribution (default: `c:70%, u:20%, d:10%`); the `before` field is `null` for `c` operations and populated (from a prior synthetic state) for `u`/`d` operations. The `after` row payload schema is defined by `PAYLOAD_TEMPLATE` (a JSON value in the ConfigMap); the shipped manifest includes a default template so events flow without any developer-authored config. Changing the template does not require rebuilding the image; schema evolution across incompatible template changes is out of scope for M1.
- **Kafka Topic**: Named channel where events are published; configurable via `KAFKA_TOPIC` (default: `cdc-events`). Acts as the canonical event bus for all downstream experiments.
- **Avro Schema**: The Debezium CDC envelope schema defining the serialization contract. Registered under subject `<topic>-value` when Schema Registry is in use. Immutable after M1 — changes require a new product spec.
- **Producer Deployment**: Kubernetes Deployment running one or more producer replicas, implemented in Python using `confluent-kafka-python`. Each replica independently produces events at the configured rate. Owned and managed via the experiment's Kubernetes manifests.
- **ConfigMap**: Kubernetes object holding producer configuration; injected as environment variables into every pod replica. The sole configuration surface — no hard-coded values allowed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer following the README from a cold clone reaches flowing events in local Kubernetes in under 30 minutes, with zero cloud dependencies and zero paid subscriptions.
- **SC-002**: The producer emits ≥ 100 messages to the configured Kafka topic within 10 seconds of pod readiness at default configuration.
- **SC-003**: Scaling to N replicas produces ≥ N × 90 events/sec total throughput as measured by message count over a 10-second window (90% of target, per-replica rate: 100/s).
- **SC-004**: All producer-owned Kubernetes resources are removed with zero orphans within 30 seconds of running the manifest delete command.
- **SC-005**: The producer makes no outbound network calls to hosts outside the local Kubernetes cluster under any configuration.
- **SC-006**: All automated tests pass with 0 failures and 0 errors before any implementation task is marked complete.

## Assumptions

- The producer is implemented in Python using `confluent-kafka-python`; tests use `pytest` per the project default.
- The developer's machine has a container runtime (Docker Desktop or equivalent), `kubectl`, `minikube`, and `helm` installed or can install them from links in the README.
- `minikube` is the primary documented local Kubernetes runtime; `kind` and Docker Desktop Kubernetes are documented as alternatives.
- The Kafka cluster and Schema Registry are deployed and managed via Helm separately from this service; this spec covers only the producer.
- All generated event data is fully synthetic — no PII, no real records, no external data sources.
- Event rate is best-effort: the producer logs a warning if it falls behind the target rate but does not crash.
- Safe replica range for local developer machines is 1–5; each pod is allocated `cpu: 100m` request / `100m` limit and `memory: 256Mi` request / `256Mi` limit. The README explains that exceeding 5 replicas without lowering the rate may saturate machine resources (5 replicas ≈ 500m CPU, 1.25Gi memory total).
- Kafka connections use plaintext with no authentication; SASL/TLS support is explicitly out of scope for M1. If a Helm-deployed Kafka requires auth, the developer must disable auth in the Helm values — the producer will not negotiate credentials.
- This service is the foundational event source for all future streaming experiments in this harness. The Avro schema it defines is a shared contract — breaking changes require a new product spec.
