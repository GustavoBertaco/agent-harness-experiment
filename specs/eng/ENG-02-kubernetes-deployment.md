# ENG-02: Container Image & Kubernetes Deployment

**Wave:** 1
**Depends on:** ENG-01 (producer module must exist and tests must pass before containerizing)

## Overview

Package the Python producer from ENG-01 into a `python:3.12-slim` Docker image and author all Kubernetes manifests required to deploy, configure, and tear down the event generator. Deliverables: `Dockerfile`, a `k8s/` directory with `deployment.yaml` and `configmap.yaml`, and a `docker-build.sh` helper. The Kubernetes manifests must satisfy all lifecycle acceptance criteria: `kubectl apply` starts events within 60 seconds of pod readiness, `kubectl scale` produces proportional throughput, and `kubectl delete` leaves no orphaned resources.

## Tech Choices

- Base image: `python:3.12-slim` (minimal attack surface, no unnecessary system packages)
- Image build: standard `docker build` — no multi-stage build required (no compiled artifacts to separate)
- Kubernetes resources: `Deployment` + `ConfigMap` only — no `Service` or `Ingress` needed (producer has no inbound traffic)
- Label selector: `app=event-generator` on all resources for clean `kubectl delete` and `kubectl get`
- ConfigMap → env vars via `envFrom.configMapRef` in the Deployment spec
- No resource limits or pod disruption budgets in v1 — keep manifests minimal

## File Layout

All files under `experiments/k8s-event-generator/`:

```
experiments/k8s-event-generator/
├── Dockerfile
├── docker-build.sh          ← builds and optionally loads image into minikube
└── k8s/
    ├── configmap.yaml
    └── deployment.yaml
```

## Implementation Steps

Follow TDD: write a failing test for each behavior → implement → verify.

1. **`Dockerfile`**
   - `FROM python:3.12-slim`
   - `WORKDIR /app`
   - Copy `requirements.txt` first (layer cache), run `pip install --no-cache-dir -r requirements.txt`
   - Copy `producer/` and `main.py`
   - `CMD ["python", "main.py"]`
   - No `ENTRYPOINT` — `CMD` only, so the pod can override the command for debugging

2. **`k8s/configmap.yaml`**
   - `kind: ConfigMap`, `metadata.name: event-generator-config`, `metadata.labels.app: event-generator`
   - `data` keys (all string values): `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC`, `EVENT_RATE_PER_SEC`, `SCHEMA_REGISTRY_URL`, `PAYLOAD_TEMPLATE`
   - Default values matching PS-001: topic = `cdc-events`, rate = `100`, schema registry = `""` (empty = raw mode)
   - `KAFKA_BOOTSTRAP_SERVERS` default: `kafka:9092` (matches Bitnami Helm chart default service name)

3. **`k8s/deployment.yaml`**
   - `kind: Deployment`, `metadata.name: event-generator`, `metadata.labels.app: event-generator`
   - `spec.replicas: 1`
   - `spec.selector.matchLabels.app: event-generator`
   - `spec.template.metadata.labels.app: event-generator`
   - Container name: `producer`, image: `event-generator:latest` (local image, `imagePullPolicy: Never` for minikube)
   - `envFrom` referencing `event-generator-config` ConfigMap
   - No liveness/readiness probes in v1 (producer has no HTTP server)
   - No resource requests/limits in v1

4. **`docker-build.sh`**
   - Build the image: `docker build -t event-generator:latest .`
   - If `minikube` is in PATH and running, also run `minikube image load event-generator:latest`
   - Print success message with the image tag

5. **Tests** — write before implementing the above:
   - `test_manifests.py`: Parse both YAML files with `pyyaml` and assert structural correctness: Deployment has `app=event-generator` label; ConfigMap has all five expected keys; `imagePullPolicy` is `Never`; `envFrom` references `event-generator-config`.
   - `test_dockerfile.py`: Parse the Dockerfile line-by-line and assert: `FROM python:3.12-slim` is the first `FROM`; `COPY requirements.txt` appears before `COPY producer/`; `CMD` includes `python main.py`.

6. **`requirements.txt`** for parsing tests: add `pyyaml` to the test dependencies (not to the producer `requirements.txt`).

## Test Plan

```
pytest experiments/k8s-event-generator/tests/test_manifests.py -v
pytest experiments/k8s-event-generator/tests/test_dockerfile.py -v
```

No live Docker or Kubernetes required — tests parse the file contents only.

| Test | Assertion |
|------|-----------|
| `test_deployment_labels` | `metadata.labels.app == "event-generator"` and `spec.selector.matchLabels.app == "event-generator"` |
| `test_configmap_keys` | All five env-var keys present in ConfigMap `data` |
| `test_image_pull_policy` | `imagePullPolicy: Never` in container spec |
| `test_env_from` | `envFrom[0].configMapRef.name == "event-generator-config"` |
| `test_dockerfile_base_image` | First `FROM` line is `python:3.12-slim` |
| `test_dockerfile_layer_order` | `requirements.txt` COPY line number < producer COPY line number |

## Acceptance Criteria

Maps to PS-001 AC-1, AC-3, AC-4, AC-5, AC-6:

- AC-1: After `kubectl apply -f k8s/` on a cluster with Kafka running, pod reaches `Running` state and events appear in the topic within 60 seconds (manual verification; documented in README as a runbook step)
- AC-3: `kubectl scale deployment/event-generator --replicas=3` → 3 pods running, each logging ~100/sec → total ≥ 270/sec (manual verification)
- AC-4: `kubectl delete -f k8s/` → `kubectl get all -l app=event-generator` returns empty
- AC-5: `kubectl logs <pod>` shows startup INFO line within 5 seconds of pod start
- AC-6: ConfigMap with invalid `SCHEMA_REGISTRY_URL` → pod logs ERROR and enters `CrashLoopBackOff`

All AC-1/3/4/5/6 items are verified during integration testing (ENG-03 covers the full runbook).

## Notes

- `imagePullPolicy: Never` is correct for minikube because the image is loaded directly into the minikube Docker daemon via `minikube image load`. For kind, the equivalent is `kind load docker-image`; document both in README.
- Do not commit the image to any registry — local only.
- The `KAFKA_BOOTSTRAP_SERVERS` default of `kafka:9092` assumes the Bitnami Helm chart is installed with release name `kafka`. If the release name differs, the user updates the ConfigMap. Document this in README.
- Do not add a Kubernetes `Service` resource — the producer has no inbound traffic.
- Do not write the README or Helm setup in this spec — that is ENG-03.
