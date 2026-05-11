"""
End-to-end integration tests for the CDC event producer.

These tests require a running minikube cluster with Kafka deployed via Helm.
They are skipped by default (`pytest.ini` sets `-m "not integration"`).

To run: pytest -m integration tests/integration/test_producer_e2e.py -v
"""
import subprocess
import time

import pytest

NAMESPACE = "kafka"
KAFKA_SVC = "kafka.kafka.svc.cluster.local:9092"
TOPIC = "cdc-events"
K8S_DIR = "k8s"
IMAGE = "cdc-event-generator:latest"


def _run(cmd: list[str], check: bool = True, capture: bool = True, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def _pod_is_running() -> bool:
    result = _run(
        ["kubectl", "get", "pods", "-l", "app=event-generator",
         "-o", "jsonpath={.items[0].status.phase}"],
        check=False,
    )
    return result.stdout.strip() == "Running"


def _wait_for_pod(timeout_sec: int = 60) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if _pod_is_running():
            return True
        time.sleep(2)
    return False


@pytest.mark.integration
class TestColdStartEventProduction:
    """User Story 1 — cold-start walkthrough produces ≥100 events in 10 seconds."""

    def setup_method(self):
        # Build image into minikube's Docker daemon
        import os
        env = os.environ.copy()
        minikube_env = subprocess.run(
            ["minikube", "docker-env", "--shell=bash"],
            capture_output=True, text=True, check=True,
        )
        for line in minikube_env.stdout.splitlines():
            if line.startswith("export "):
                key, _, val = line[7:].partition("=")
                env[key] = val.strip('"')

        subprocess.run(
            ["docker", "build", "-t", IMAGE, "."],
            check=True, env=env,
        )
        _run(["kubectl", "apply", "-f", f"{K8S_DIR}/configmap.yaml"])
        _run(["kubectl", "apply", "-f", f"{K8S_DIR}/deployment.yaml"])

    def teardown_method(self):
        _run(["kubectl", "delete", "-f", f"{K8S_DIR}/deployment.yaml"], check=False)
        _run(["kubectl", "delete", "-f", f"{K8S_DIR}/configmap.yaml"], check=False)

    def test_pod_reaches_running(self):
        assert _wait_for_pod(timeout_sec=60), "Pod did not reach Running state within 60s"

    def test_produces_100_messages_in_10_seconds(self):
        assert _wait_for_pod(timeout_sec=60), "Pod did not reach Running state"

        result = _run(
            [
                "kubectl", "run", "kafka-consumer-test", "--rm", "--attach",
                "--image=bitnami/kafka:latest",
                "--restart=Never",
                f"--namespace={NAMESPACE}",
                "--",
                "kafka-console-consumer.sh",
                f"--bootstrap-server={KAFKA_SVC}",
                f"--topic={TOPIC}",
                "--from-beginning",
                "--max-messages", "100",
                "--timeout-ms", "10000",
            ],
            timeout=30,
            check=False,
        )
        # kafka-console-consumer exits 0 when max-messages reached, non-zero on timeout
        assert result.returncode == 0, (
            f"Consumer did not receive 100 messages within 10s.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


@pytest.mark.integration
class TestHorizontalScaling:
    """User Story 3 — 3 replicas produce ≥270 events in 10 seconds."""

    def setup_method(self):
        _run(["kubectl", "apply", "-f", f"{K8S_DIR}/configmap.yaml"])
        _run(["kubectl", "apply", "-f", f"{K8S_DIR}/deployment.yaml"])
        _run(["kubectl", "scale", "deployment/event-generator", "--replicas=3"])

    def teardown_method(self):
        _run(["kubectl", "delete", "-f", f"{K8S_DIR}/deployment.yaml"], check=False)
        _run(["kubectl", "delete", "-f", f"{K8S_DIR}/configmap.yaml"], check=False)

    def test_three_replicas_produce_270_messages_in_10_seconds(self):
        # Wait for all 3 replicas to be ready
        import subprocess as _sp
        deadline = time.monotonic() + 90
        ready = 0
        while time.monotonic() < deadline and ready < 3:
            r = _run(
                ["kubectl", "get", "deployment", "event-generator",
                 "-o", "jsonpath={.status.readyReplicas}"],
                check=False,
            )
            try:
                ready = int(r.stdout.strip() or "0")
            except ValueError:
                ready = 0
            if ready < 3:
                time.sleep(3)

        assert ready == 3, f"Only {ready}/3 replicas ready within 90s"

        result = _run(
            [
                "kubectl", "run", "kafka-consumer-scale-test", "--rm", "--attach",
                "--image=bitnami/kafka:latest",
                "--restart=Never",
                f"--namespace={NAMESPACE}",
                "--",
                "kafka-console-consumer.sh",
                f"--bootstrap-server={KAFKA_SVC}",
                f"--topic={TOPIC}",
                "--max-messages", "270",
                "--timeout-ms", "10000",
            ],
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, (
            f"Consumer did not receive 270 messages within 10s.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


@pytest.mark.integration
class TestCleanTeardown:
    """User Story 4 — kubectl delete -f k8s/ removes all producer-owned resources."""

    def test_no_resources_remain_after_delete(self):
        _run(["kubectl", "apply", "-f", f"{K8S_DIR}/configmap.yaml"])
        _run(["kubectl", "apply", "-f", f"{K8S_DIR}/deployment.yaml"])
        assert _wait_for_pod(timeout_sec=60), "Pod did not reach Running before teardown"

        _run(["kubectl", "delete", "-f", f"{K8S_DIR}/deployment.yaml"])
        _run(["kubectl", "delete", "-f", f"{K8S_DIR}/configmap.yaml"])

        deadline = time.monotonic() + 30
        empty = False
        while time.monotonic() < deadline:
            r = _run(
                ["kubectl", "get", "all", "-l", "app=event-generator", "--no-headers"],
                check=False,
            )
            if not r.stdout.strip():
                empty = True
                break
            time.sleep(2)

        assert empty, "Resources with label app=event-generator still exist after delete"
