# PS-001: Kubernetes-Deployed Synthetic CDC Event Generator

**Status:** Approved
**Author:** Gustavo Beserra Bertaco
**Date:** 2026-05-05
**Experiment:** experiments/k8s-event-generator/

---

## Intent

Build a configurable, locally-deployed Kubernetes service that generates synthetic Debezium CDC-style events serialized in Avro format and publishes them to a local Kafka topic. The service defaults to 100 events/sec (1 event per 10ms) and is tunable via ConfigMap and environment variables. This is not a one-off prototype — it is the foundational, reusable event source for all future streaming experiments in this harness. Every future consumer, processor, or pipeline experiment builds on top of what this service emits. The service must be self-contained and reproducible: a developer who clones the repo cold and follows the prerequisite docs must be producing events within minutes, with zero cloud or subscription costs.

---

## Problem

There is no standard event source in this harness. Every streaming experiment that follows would need to invent its own producer from scratch — choosing a schema, a serialization format, a Kafka client, and a deployment model — producing incompatible, non-reusable artifacts. This service eliminates that duplication by providing a canonical, schema-registered, Kubernetes-native event producer that every future experiment can treat as a given.

**Affected users / personas:**
- **Harness developer (any OS):** Wants to run a streaming experiment locally. Currently has no event source to subscribe to. Must install prerequisites from scratch — needs clear documentation that can be followed without prior Kubernetes or Kafka expertise, or handed to an AI assistant to execute.
- **Future agent implementing a consumer experiment:** Needs a well-defined Kafka topic and Avro schema to write tests against. Without this service, the agent must mock or stub the event source, reducing fidelity.

---

## Goals

Measurable conditions that define success. Every goal must be verifiable.

- [ ] `kubectl apply -f experiments/k8s-event-generator/k8s/` deploys the producer Deployment successfully and events begin flowing to the configured Kafka topic within 60 seconds of pod readiness.
- [ ] A Kafka CLI consumer (`kubectl exec` into a pod) confirms ≥ 100 messages arrive on the target topic within 10 seconds of producer startup, with zero cloud dependencies.
- [ ] Scaling replicas (`kubectl scale deployment/event-generator --replicas=N`) produces proportional throughput increase, verifiable via message count in Kafka.
- [ ] `kubectl delete -f experiments/k8s-event-generator/k8s/` removes all producer resources cleanly (no orphaned pods, ConfigMaps, or Services remain).
- [ ] The producer registers the Avro schema with the local Confluent Schema Registry on startup; schema is queryable at `http://localhost:<schema-registry-port>/subjects`.
- [ ] All producer behavior is covered by `pytest` tests that run before implementation code is written (TDD).
- [ ] Zero cloud or subscription costs under any configuration path.

---

## Non-Goals

Explicitly out of scope for v1. Being explicit here prevents scope creep in agent implementation.

- Event consumers — deferred to future milestones; this service only produces.
- Persistence or storage beyond Kafka's configured retention window.
- Authentication or authorization on any component (Kafka, Schema Registry, producer).
- Monitoring dashboards or alerting (e.g., Grafana, Prometheus) — not in scope for v1.
- Complex or multi-table schemas beyond a single Debezium CDC Avro envelope.
- Dead-letter queues or retry logic for failed Kafka publishes.
- Anything that incurs cloud or subscription costs in any configuration path.
- Multi-cluster or remote Kubernetes targets — local machine only.

---

## Expected Behavior

Happy path, written as a sequence of events:

1. Developer clones the repo. Opens `experiments/k8s-event-generator/README.md`. Follows the **Prerequisites** section, which lists: Docker Desktop (or equivalent container runtime), `kubectl`, `minikube` or `kind` (default documented), and `helm`. The README includes the exact install commands or links so a developer (or AI assistant) can set up a clean machine without prior context.
2. Developer runs the documented `helm install` commands to stand up a local Kafka cluster (Bitnami Kafka Helm chart) and Confluent Schema Registry in Kubernetes. Both reach `Running` state.
3. Developer runs `kubectl apply -f experiments/k8s-event-generator/k8s/` to deploy the Python producer Deployment and its ConfigMap.
4. On startup, the producer pod reads its configuration from environment variables (sourced from the ConfigMap): `KAFKA_BOOTSTRAP_SERVERS`, `SCHEMA_REGISTRY_URL`, `KAFKA_TOPIC`, `EVENT_RATE_PER_SEC`, and `PAYLOAD_TEMPLATE`.
5. If `SCHEMA_REGISTRY_URL` is set, the producer registers the Debezium CDC Avro schema with Schema Registry on startup and uses the wire format (magic byte + schema ID). If `SCHEMA_REGISTRY_URL` is unset or empty, the producer runs in raw Avro mode — no Schema Registry required. If Schema Registry is configured but unreachable, the pod logs a clear error and exits with code 1.
6. The producer begins emitting synthetic Debezium CDC-style events to the configured Kafka topic at the configured rate (default: 100 events/sec). Each event is serialized in Avro using the registered schema.
7. Developer runs `kubectl exec -it <kafka-pod> -- kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic <topic> --from-beginning` and sees messages flowing.
8. Developer scales: `kubectl scale deployment/event-generator --replicas=3`. Throughput increases proportionally to ~300 events/sec across the three pods. Each pod logs its own per-replica rate.
9. Developer runs `kubectl delete -f experiments/k8s-event-generator/k8s/`. All producer resources are removed. Kafka and Schema Registry remain (managed separately via Helm).

**Edge cases to handle:**

- **Pod crashes silently:** Producer must log structured startup and per-batch status lines so `kubectl logs` always shows the last known state. Pod must not run silently without emitting logs.
- **Event rate drifts under load:** Rate is best-effort. If the producer falls behind its target rate, it logs a warning: `WARN: target rate 100/s, achieved rate X/s`. It does not error or crash — it keeps running.
- **Misconfigured replica count floods the system:** README documents a safe default replica range (1–5 for local machines) and explains that each replica runs at the full configured rate, so total throughput = replicas × rate. Users are warned to lower `EVENT_RATE_PER_SEC` before scaling high.
- **Schema Registry unavailable at startup:** Producer exits with code 1 and logs `ERROR: could not reach Schema Registry at <url> — aborting`. Kubernetes restarts the pod; `kubectl describe pod` shows the restart count and reason.
- **Kafka broker unavailable:** Producer logs `ERROR: could not connect to Kafka at <bootstrap> — retrying` with exponential backoff (max 5 retries), then exits with code 1.

---

## Acceptance Criteria

Machine-verifiable. Each criterion maps to a runnable test or command.

| ID   | Criterion | Verification |
|------|-----------|--------------|
| AC-1 | Producer emits ≥ 100 messages to the Kafka topic within 10 seconds of pod readiness | `kubectl exec -it <kafka-pod> -- kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic <topic> --max-messages 100 --timeout-ms 10000` exits 0 |
| AC-2 | When `SCHEMA_REGISTRY_URL` is set, Avro schema is registered on startup; when unset, producer runs in raw Avro mode without contacting Schema Registry | (a) with URL set: `curl http://localhost:<schema-registry-port>/subjects` returns topic subject; (b) without URL: producer pod starts and emits events with no Schema Registry running |
| AC-3 | Scaling to N replicas produces N × (configured rate) messages/sec | `kubectl scale deployment/event-generator --replicas=3` then count messages over 10s; assert count ≥ 3 × 100 × 10 × 0.9 (10% tolerance) |
| AC-4 | `kubectl delete -f k8s/` removes all producer-owned resources | `kubectl get all -l app=event-generator` returns empty after deletion |
| AC-5 | Pod logs are always present and structured | `kubectl logs <pod>` shows at least one startup log line and one per-batch status line within 5 seconds of pod start |
| AC-6 | Pod exits with code 1 and logs error when Schema Registry is unreachable | Set `SCHEMA_REGISTRY_URL` to an invalid host; `kubectl describe pod` shows `CrashLoopBackOff` and `kubectl logs` shows the error message |
| AC-7 | All pytest unit tests pass | `pytest experiments/k8s-event-generator/tests/ -v` → 0 failures, 0 errors |
| AC-8 | No cloud or external network calls are made by the producer | Run `kubectl exec` into the pod and confirm no outbound traffic to non-cluster IPs (verify via logs or network policy) |

---

## Technical Constraints

| Area | Constraint |
|------|------------|
| Language | Python 3.12 |
| Kafka client | `confluent-kafka-python` (preferred) or `kafka-python` — agent selects lightest fit for Avro + Schema Registry integration and documents the choice |
| Avro serialization | `fastavro` for schema serialization; Schema Registry integration is **optional** — producer works in two modes: (1) raw Avro bytes (no Schema Registry required, default for v1), (2) Schema Registry wire format (magic byte + schema ID prefix, enabled via `SCHEMA_REGISTRY_URL` env var) |
| Kafka cluster | Bitnami Kafka Helm chart (local, free, no Zookeeper mode preferred) |
| Schema Registry | Confluent Schema Registry via Helm (local, free) |
| Container base image | `python:3.12-slim` |
| Kubernetes runtime | minikube (default and primary documented runtime); kind and Docker Desktop K8s listed as alternatives in README |
| Configuration surface | Kubernetes ConfigMap + environment variables; Helm `values.yaml` for Kafka and Schema Registry |
| Configurable knobs | `EVENT_RATE_PER_SEC` (default: 100), `KAFKA_TOPIC` (default: `cdc-events`), `KAFKA_BOOTSTRAP_SERVERS`, `SCHEMA_REGISTRY_URL`, `PAYLOAD_TEMPLATE` (default: built-in synthetic record) |
| Platform target | Local developer machine (any OS with container runtime — macOS, Windows, Linux) |
| Test runner | `pytest` |
| Cost | Zero cloud or subscription costs under any configuration path |
| Data privacy | All data is synthetic — no PII, no real records |

---

## Event Payload Format

All events conform to a Debezium CDC Avro envelope. The Avro schema must be registered with Schema Registry under the subject `<KAFKA_TOPIC>-value` before any messages are produced.

**Schema structure:**

```json
{
  "type": "record",
  "name": "Envelope",
  "namespace": "com.harness.cdc",
  "fields": [
    {"name": "before", "type": ["null", {"type": "record", "name": "Row", "fields": [
      {"name": "id", "type": "string"},
      {"name": "text", "type": "string"},
      {"name": "created_at", "type": "long"}
    ]}], "default": null},
    {"name": "after", "type": ["null", "Row"], "default": null},
    {"name": "op", "type": "string"},
    {"name": "ts_ms", "type": "long"},
    {"name": "source", "type": {"type": "record", "name": "Source", "fields": [
      {"name": "name", "type": "string"},
      {"name": "ts_ms", "type": "long"},
      {"name": "db", "type": "string"},
      {"name": "table", "type": "string"}
    ]}}
  ]
}
```

- `op` values: `c` (create), `u` (update), `d` (delete), `r` (read/snapshot). Synthetic generator uses `c` by default; distribution is configurable via `PAYLOAD_TEMPLATE`.
- `after.id`: UUID v4 string, generated fresh per event.
- `after.text`: Random alphanumeric string, 32 characters.
- `after.created_at`: Unix epoch milliseconds at event generation time.
- `source.name`: Value of `KAFKA_TOPIC` env var.
- `source.db`: `"synthetic"`.
- `source.table`: `"events"`.
- `ts_ms`: Unix epoch milliseconds at event generation time.

---

## Boundaries

Three-tier system — agents must follow this exactly.

**Always do:**
- Write tests before implementation code (TDD — failing test first, then minimum code to pass, then refactor).
- Use type hints in all Python code.
- Use branch naming `wave-N/ENG-NN-<slug>` (e.g., `wave-1/ENG-01-producer`).
- Reference the spec ID in every commit message (e.g., `ENG-01: implement Avro schema registration`).
- Write a `README.md` inside `experiments/k8s-event-generator/` with prerequisites, install steps, run steps, and safe replica limits.
- Log structured status lines (startup confirmation, per-batch rate, warnings, errors) — never run silently.
- Keep all experiment code inside `experiments/k8s-event-generator/` unless the spec explicitly specifies another path.
- Run `pytest experiments/k8s-event-generator/tests/` and confirm 0 failures before marking any task done.

**Ask before doing:**
- Ask before choosing between `confluent-kafka-python` and `kafka-python` — state the tradeoff clearly and wait for confirmation if both are viable.
- Ask before defaulting the local Kubernetes runtime in documentation (minikube vs kind vs Docker Desktop K8s) — see Open Questions.
- Ask before making Schema Registry optional (raw Avro vs registered schema) — see Open Questions.
- Ask before adding any dependency not listed in Technical Constraints.
- Ask before writing any file outside `experiments/k8s-event-generator/`.

**Never do:**
- Never incur cloud or subscription costs under any configuration path.
- Never write files outside `experiments/k8s-event-generator/` unless the spec explicitly authorizes it.
- Never skip tests or acceptance criteria — surface unmet criteria as blockers, not silent omissions.
- Never hard-code credentials, cluster addresses, or topic names — always use ConfigMap / env vars.
- Never use mocked Kafka or Schema Registry in integration tests — use a real local instance spun up for the test run.
- Never resolve open questions with assumptions — surface them as blockers.

---

## Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| 1 | Which local Kubernetes runtime should be featured as the default in documentation? | Gustavo Beserra Bertaco | **Resolved:** minikube is the default; kind and Docker Desktop K8s documented as alternatives. |
| 2 | Is Schema Registry required for v1? | Gustavo Beserra Bertaco | **Resolved:** Optional. Raw Avro is the default mode; Schema Registry mode enabled when `SCHEMA_REGISTRY_URL` is set. |

> All open questions resolved. This spec is ready for engineering spec authoring and `/build-wave`.

---

## Dependencies

- No dependencies on existing repo experiments — this is the first milestone and is greenfield.
- **Bitnami Kafka Helm chart** — must be installable from the Bitnami Helm repo with a single `helm install` command; no internet access after initial chart pull is required.
- **Confluent Schema Registry Helm chart** — must be installable locally; agent documents the exact Helm repo and chart name.
- **Future dependency (reverse):** All future consumer, processor, and pipeline experiments in this harness will depend on the Kafka topic and Avro schema produced by this service. Changes to the schema after M1 are breaking changes and require a new PS.

---

## Milestones

| Milestone | Description | Done when |
|-----------|-------------|-----------|
| M1 | Spec finalized and engineering specs written | All open questions resolved; ENG specs written and reviewed; no unresolved questions remain |
| M2 | Local infrastructure up | Bitnami Kafka and Confluent Schema Registry running in local Kubernetes; `helm install` documented and tested end-to-end |
| M3 | Producer service running | Python producer deployed via `kubectl apply`; schema registered; events flowing at ≥ 100/sec; all AC-1 through AC-8 pass; `pytest` green |
| M4 | Scaling and cleanup verified | `kubectl scale` produces proportional throughput; `kubectl delete` cleans up all resources; README complete with prerequisites, run steps, and safe replica guidance |
