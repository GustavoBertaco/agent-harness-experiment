# CDC Event Generator — Kubernetes Experiment

Synthetic Debezium-compatible CDC event producer deployed to a local Kubernetes cluster. Emits Avro-encoded events to Kafka at a configurable rate (default 100 events/sec per replica) with no cloud dependencies.

---

## Prerequisites

| Tool           | Minimum version | Install                                          |
|----------------|-----------------|--------------------------------------------------|
| Docker Desktop | 4.x             | https://docs.docker.com/desktop/                 |
| minikube       | 1.32+           | https://minikube.sigs.k8s.io/docs/start/         |
| kubectl        | 1.28+           | https://kubernetes.io/docs/tasks/tools/          |
| Helm           | 3.12+           | https://helm.sh/docs/intro/install/              |
| Python         | 3.11+           | https://www.python.org/downloads/                |

**Alternatives to minikube**: `kind` or Docker Desktop's built-in Kubernetes work identically — substitute wherever `minikube` appears below.

---

## Step 1 — Start minikube

```bash
minikube start --cpus=4 --memory=4096
kubectl cluster-info   # verify
```

---

## Step 2 — Deploy Kafka via Helm

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm install kafka bitnami/kafka \
  --set listeners.client.protocol=PLAINTEXT \
  --set listeners.external.protocol=PLAINTEXT \
  --namespace kafka --create-namespace \
  --wait

kubectl get pods -n kafka   # all pods should be Running/Ready
```

---

## Step 3 — Build the producer image

From this directory (`experiments/k8s-cdc-event-generator/`):

```bash
eval $(minikube docker-env)          # point Docker at minikube's daemon
docker build -t cdc-event-generator:latest .
```

> Run `eval $(minikube docker-env)` in every new shell before building — it makes the image available inside minikube without a registry push.

---

## Step 4 — Deploy the producer

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml

kubectl get pods -l app=event-generator   # STATUS should be Running
kubectl logs -l app=event-generator --tail=20   # config summary + "Producer started"
```

---

## Step 5 — Confirm events are flowing

```bash
kubectl run kafka-consumer --rm -it \
  --image=bitnami/kafka:latest \
  --restart=Never \
  --namespace=kafka \
  -- kafka-console-consumer.sh \
     --bootstrap-server kafka.kafka.svc.cluster.local:9092 \
     --topic cdc-events \
     --from-beginning \
     --max-messages 10
```

You should see 10 messages within seconds. Messages are binary Avro — bytes look garbled in a plain consumer, but the count confirms the producer is working.

---

## Configuration

All configuration lives in `k8s/configmap.yaml`. Edit the ConfigMap and delete the pod to apply changes — the Deployment restarts it automatically.

| Env var                   | Default                              | Description                                        |
|---------------------------|--------------------------------------|----------------------------------------------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka.kafka.svc.cluster.local:9092` | Kafka broker address                               |
| `KAFKA_TOPIC`             | `cdc-events`                         | Topic to produce events to                         |
| `EVENT_RATE_PER_SEC`      | `100`                                | Target events per second per replica               |
| `SCHEMA_REGISTRY_URL`     | *(empty)*                            | Leave empty for raw Avro mode (default)            |
| `PAYLOAD_TEMPLATE`        | *(default JSON)*                     | JSON defining Row fields and generator tokens      |
| `OP_WEIGHTS`              | `c:70,u:20,d:10`                     | CDC operation distribution (must sum to 100)       |

---

## Horizontal Scaling

```bash
kubectl scale deployment event-generator --replicas=3
```

Each replica independently produces at `EVENT_RATE_PER_SEC`. Total throughput ≈ replicas × rate.

**Safe replica range**: 1–5 on a typical developer machine (4 CPUs, 8 GB RAM). Each pod uses `cpu: 100m` / `memory: 256Mi`. Exceeding 5 replicas without reducing the rate may saturate the machine.

Check per-pod throughput:

```bash
kubectl logs -l app=event-generator --prefix=true | grep "rate="
```

Each line is prefixed with the pod name, showing individual replica throughput. With 3 replicas at the default 100 events/sec, expect ≥270 total events per second across the topic.

Scale back to 1 replica:

```bash
kubectl scale deployment event-generator --replicas=1
```

---

## Schema Registry mode (optional)

Deploy Schema Registry alongside Kafka:

```bash
helm install schema-registry bitnami/schema-registry \
  --set kafka.bootstrapServers=kafka.kafka.svc.cluster.local:9092 \
  --namespace kafka \
  --wait
```

Set `SCHEMA_REGISTRY_URL` in `k8s/configmap.yaml`:

```yaml
SCHEMA_REGISTRY_URL: "http://schema-registry.kafka.svc.cluster.local:8081"
```

Delete the pod to restart in SR mode:

```bash
kubectl delete pod -l app=event-generator
```

The schema registers under subject `cdc-events-value` on startup. Events carry the 5-byte Confluent wire-format prefix. The startup log will show `mode=schema-registry url=<url>`.

---

## Teardown

Remove all producer-owned resources (Kafka is unaffected):

```bash
kubectl delete -f k8s/
```

Verify nothing remains:

```bash
kubectl get all -l app=event-generator
# Expected: No resources found.
```

To tear down Kafka as well:

```bash
helm uninstall kafka -n kafka
kubectl delete namespace kafka
```

---

## Running tests

Unit tests (no Kubernetes required):

```bash
pip install -r requirements-dev.txt
pytest tests/unit -v
```

Integration tests (requires running minikube + Kafka):

```bash
pytest -m integration tests/integration/test_producer_e2e.py -v
```
