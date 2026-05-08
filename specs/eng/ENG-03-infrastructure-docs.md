# ENG-03: Infrastructure Setup & Developer README

**Wave:** 1
**Depends on:** ENG-01, ENG-02 (README references the producer module and k8s manifests; all paths must exist)

## Overview

Author the `experiments/k8s-event-generator/README.md` that lets a developer (or an AI assistant) cold-start the entire stack from scratch — zero prior Kubernetes or Kafka expertise required. The README covers: prerequisite installation (Docker, kubectl, minikube, helm), standing up Kafka and Schema Registry via Helm, building and loading the producer image, deploying via `kubectl apply`, verifying events flow, scaling, and tearing down. This spec also defines the exact Helm chart references and `values.yaml` overrides needed for Kafka and Schema Registry, stored as `infra/kafka-values.yaml` and `infra/schema-registry-values.yaml`.

## Tech Choices

- Kafka: Bitnami Kafka Helm chart (`bitnami/kafka`, KRaft mode — no Zookeeper), release name `kafka`
- Schema Registry: Confluent Schema Registry Helm chart (`confluentinc/cp-schema-registry`), release name `schema-registry`
- Default Kubernetes runtime: minikube; kind and Docker Desktop K8s documented as alternatives
- Helm repo references are pinned by chart name and repo URL — no version pin in v1 (use latest stable)

## File Layout

All files under `experiments/k8s-event-generator/`:

```
experiments/k8s-event-generator/
├── README.md
└── infra/
    ├── kafka-values.yaml             ← Bitnami Kafka overrides for local single-node
    └── schema-registry-values.yaml  ← Confluent Schema Registry overrides
```

## Implementation Steps

Follow TDD: write tests for the README structure and Helm values files, then write the content.

1. **`infra/kafka-values.yaml`**
   - Single broker (`replicaCount: 1`)
   - KRaft mode (set `kraft.enabled: true` if the chart requires it, or omit Zookeeper-related settings)
   - Disable persistence (`persistence.enabled: false`) to avoid PVC issues on local clusters
   - Expose via ClusterIP service (default); `listeners.client.protocol: PLAINTEXT`
   - `fullnameOverride: kafka` to ensure the service is reachable at `kafka:9092` from within the cluster

2. **`infra/schema-registry-values.yaml`**
   - `replicaCount: 1`
   - `kafka.bootstrapServers: PLAINTEXT://kafka:9092` pointing at the Bitnami release
   - No authentication
   - `fullnameOverride: schema-registry` for a stable in-cluster hostname

3. **`README.md`** — Sections in order:

   **Prerequisites**
   List with install links and exact commands for macOS/Windows/Linux:
   - Docker Desktop (or OrbStack on macOS, Rancher Desktop as alternative)
   - kubectl
   - minikube (`minikube start --driver=docker`)
   - helm (`brew install helm` / winget / Linux package)
   - Python 3.12 (for running tests locally before deploying)

   **Alternative runtimes**
   Brief callout: kind (`kind create cluster`) and Docker Desktop K8s (enable in settings) work as drop-in replacements; replace `minikube image load` with `kind load docker-image` for kind.

   **1. Start local Kubernetes**
   ```bash
   minikube start --driver=docker
   ```

   **2. Install Kafka**
   ```bash
   helm repo add bitnami https://charts.bitnami.com/bitnami
   helm repo update
   helm install kafka bitnami/kafka -f experiments/k8s-event-generator/infra/kafka-values.yaml
   ```
   Wait for pod readiness: `kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=kafka --timeout=120s`

   **3. Install Schema Registry (optional — raw Avro mode skips this)**
   ```bash
   helm repo add confluentinc https://packages.confluent.io/helm
   helm repo update
   helm install schema-registry confluentinc/cp-schema-registry -f experiments/k8s-event-generator/infra/schema-registry-values.yaml
   ```
   Wait: `kubectl wait --for=condition=ready pod -l app=cp-schema-registry --timeout=120s`

   **4. Build and load the producer image**
   ```bash
   cd experiments/k8s-event-generator
   bash docker-build.sh
   ```

   **5. Deploy the producer**
   ```bash
   kubectl apply -f experiments/k8s-event-generator/k8s/
   ```
   Expected: pod reaches `Running` within 60 seconds. Check: `kubectl get pods -l app=event-generator`

   **6. Verify events are flowing**
   ```bash
   kubectl exec -it $(kubectl get pod -l app.kubernetes.io/name=kafka -o name | head -1) -- \
     kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic cdc-events --max-messages 10 --timeout-ms 5000
   ```

   **7. Scale the producer**
   ```bash
   kubectl scale deployment/event-generator --replicas=3
   ```
   Total throughput becomes ~300 events/sec. **Safe replica range: 1–5 on a local machine.** Each replica runs at the full `EVENT_RATE_PER_SEC`. Lower the rate before scaling high: edit `configmap.yaml` and re-apply.

   **8. Tear down**
   ```bash
   kubectl delete -f experiments/k8s-event-generator/k8s/
   # Kafka and Schema Registry remain; to remove them:
   helm uninstall kafka
   helm uninstall schema-registry
   minikube stop   # or minikube delete to fully reset
   ```

   **Troubleshooting**
   - Pod in `CrashLoopBackOff`: `kubectl logs <pod>` — check for `ERROR: could not reach Schema Registry` or `ERROR: could not connect to Kafka`
   - Kafka not reachable: confirm `KAFKA_BOOTSTRAP_SERVERS` in ConfigMap matches the Helm release service name
   - Image not found: run `bash docker-build.sh` again and confirm `minikube image load` succeeded

   **Running tests**
   ```bash
   cd experiments/k8s-event-generator
   pip install -r requirements.txt
   pytest tests/ -v
   ```

4. **Tests** — write before writing the README:
   - `test_readme.py`: Read `README.md` and assert sections exist: `Prerequisites`, `Install Kafka`, `Deploy`, `Verify`, `Scale`, `Tear down`, `Troubleshooting`, `Running tests`. Assert the kafka Helm command is present. Assert `safe replica range` warning text is present.
   - `test_helm_values.py`: Parse both YAML files with `pyyaml`. Assert `kafka-values.yaml` has `persistence.enabled: false` and `replicaCount: 1`. Assert `schema-registry-values.yaml` has `kafka.bootstrapServers` pointing to `kafka:9092`.

## Test Plan

```
pytest experiments/k8s-event-generator/tests/test_readme.py -v
pytest experiments/k8s-event-generator/tests/test_helm_values.py -v
```

No live infrastructure required — tests inspect file contents only.

| Test | Assertion |
|------|-----------|
| `test_readme_has_prerequisites` | "Prerequisites" section present in README |
| `test_readme_has_safe_replica_warning` | Text matching `safe replica` in README |
| `test_readme_has_kafka_helm_command` | `helm install kafka bitnami/kafka` in README |
| `test_readme_has_teardown` | "Tear down" or "uninstall" section present |
| `test_kafka_values_no_persistence` | `persistence.enabled == False` in kafka-values.yaml |
| `test_kafka_values_single_broker` | `replicaCount == 1` in kafka-values.yaml |
| `test_schema_registry_bootstrap` | `kafka.bootstrapServers` contains `kafka:9092` |

## Acceptance Criteria

Maps to PS-001 AC-1, AC-3, AC-4 (runbook coverage):

- A developer following the README cold from a clean machine reaches a running producer with events flowing (manual verification; agent does not need to run this on the developer's machine)
- README safe replica warning is present and accurate (`replicas × EVENT_RATE_PER_SEC = total throughput`)
- All pytest tests in `test_readme.py` and `test_helm_values.py` pass

## Notes

- Do not add Helm values for authentication, TLS, or monitoring — out of scope for v1 per PS-001 Non-Goals.
- Helm chart version is not pinned in v1. If the chart API changes in a future Bitnami release, update `kafka-values.yaml` rather than pinning an old chart.
- The `kubectl exec` Kafka consumer command differs between KRaft Bitnami and legacy Zookeeper Bitnami. Use the KRaft form (`kafka-console-consumer.sh` with `--bootstrap-server`) as shown.
- Do not write a `docker-compose.yaml` — the spec targets Kubernetes only.
- The README must be complete enough that an AI assistant (with no prior context) can execute it step by step and reach a working setup.
