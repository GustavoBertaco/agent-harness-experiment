# Quickstart: Kubernetes CDC Event Generator

**Audience**: Developer setting up for the first time  
**Time to first events**: < 30 minutes from cold clone  
**Cloud dependencies**: None

---

## Prerequisites

Install the following tools before starting. All are free and run locally.

| Tool            | Version (minimum) | Install link                                       |
|-----------------|-------------------|----------------------------------------------------|
| Docker Desktop  | 4.x               | https://docs.docker.com/desktop/                   |
| minikube        | 1.32+             | https://minikube.sigs.k8s.io/docs/start/           |
| kubectl         | 1.28+             | https://kubernetes.io/docs/tasks/tools/             |
| Helm            | 3.12+             | https://helm.sh/docs/intro/install/                |
| Python          | 3.11+             | https://www.python.org/downloads/                  |

**Alternatives to minikube**: `kind` or Docker Desktop's built-in Kubernetes are both supported. Steps are identical — substitute `kind` or enable Desktop Kubernetes where `minikube` is mentioned.

---

## Step 1 — Start a local Kubernetes cluster

```bash
minikube start --cpus=4 --memory=4096
```

Verify:
```bash
kubectl cluster-info
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
```

Verify Kafka is ready:
```bash
kubectl get pods -n kafka
# All pods should show Running/Ready
```

---

## Step 3 — Build the producer image

From the repo root:
```bash
cd experiments/k8s-cdc-event-generator
eval $(minikube docker-env)          # point Docker to minikube's daemon
docker build -t cdc-event-generator:latest .
```

> **Note**: `eval $(minikube docker-env)` makes the image available inside minikube without a registry. Run this in every new shell session before building.

---

## Step 4 — Deploy the producer

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
```

Verify the pod is running:
```bash
kubectl get pods -l app=event-generator
# Expected: STATUS=Running
```

Check startup logs:
```bash
kubectl logs -l app=event-generator --tail=20
# Expected: config summary + "Producer started" line
```

---

## Step 5 — Confirm events are flowing

Open a Kafka consumer (runs inside the cluster):
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

You should see 10 messages within seconds. Each message is binary-encoded Avro — the bytes will look garbled in a plain consumer but the count confirms the producer is working.

---

## Configuration reference

All configuration is in `k8s/configmap.yaml`. Edit the ConfigMap and delete the pod to apply changes (the Deployment will restart it automatically).

| Env var                  | Default         | Description                                           |
|--------------------------|-----------------|-------------------------------------------------------|
| `KAFKA_BOOTSTRAP_SERVERS`| `kafka.kafka.svc.cluster.local:9092` | Kafka broker address |
| `KAFKA_TOPIC`            | `cdc-events`    | Topic to produce events to                            |
| `EVENT_RATE_PER_SEC`     | `100`           | Target events per second per replica                  |
| `SCHEMA_REGISTRY_URL`    | *(empty)*       | Leave empty for raw Avro mode (default)               |
| `PAYLOAD_TEMPLATE`       | *(default JSON)*| JSON defining Row fields and generators               |
| `OP_WEIGHTS`             | `c:70,u:20,d:10`| CDC operation distribution (must sum to 100)          |

---

## Scaling

```bash
kubectl scale deployment event-generator --replicas=3
```

Each replica independently produces at `EVENT_RATE_PER_SEC`. Total throughput ≈ replicas × rate.

**Safe replica range**: 1–5 replicas on a typical developer machine (4 CPUs, 8 GB RAM). Each pod uses `cpu: 100m` and `memory: 256Mi`. Exceeding 5 replicas without lowering the rate may saturate your machine.

Check per-pod throughput:
```bash
kubectl logs -l app=event-generator --prefix=true | grep "rate="
```

---

## Schema Registry mode (optional)

To enable Confluent Schema Registry, deploy it alongside Kafka:

```bash
helm install schema-registry bitnami/schema-registry \
  --set kafka.bootstrapServers=kafka.kafka.svc.cluster.local:9092 \
  --namespace kafka \
  --wait
```

Then set `SCHEMA_REGISTRY_URL` in the ConfigMap:
```yaml
SCHEMA_REGISTRY_URL: "http://schema-registry.kafka.svc.cluster.local:8081"
```

Delete the producer pod to restart with SR mode:
```bash
kubectl delete pod -l app=event-generator
```

The schema is registered under subject `cdc-events-value` on startup. Events will use the 5-byte Confluent wire format prefix.

---

## Teardown

Remove all producer resources (Kafka is unaffected):
```bash
kubectl delete -f k8s/deployment.yaml
kubectl delete -f k8s/configmap.yaml

# Verify nothing remains
kubectl get all -l app=event-generator
# Expected: No resources found.
```

To tear down Kafka as well:
```bash
helm uninstall kafka -n kafka
kubectl delete namespace kafka
```
