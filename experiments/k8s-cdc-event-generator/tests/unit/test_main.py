import logging
import os
import sys
import pytest


def _base_env():
    return {
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
        "KAFKA_TOPIC": "cdc-events",
        "EVENT_RATE_PER_SEC": "100",
        "SCHEMA_REGISTRY_URL": "",
        "OP_WEIGHTS": "c:70,u:20,d:10",
    }


def _apply_env(env, monkeypatch):
    for k, v in env.items():
        monkeypatch.setenv(k, v)


# ---------------------------------------------------------------------------
# T018a – Kafka connect with exponential backoff → SystemExit(1) after 5 failures
# ---------------------------------------------------------------------------

class TestKafkaConnectRetry:
    def test_exits_1_after_5_kafka_failures(self, monkeypatch, caplog):
        from confluent_kafka import KafkaException
        _apply_env(_base_env(), monkeypatch)

        call_count = {"n": 0}

        def mock_producer_ctor(*args, **kwargs):
            call_count["n"] += 1
            raise KafkaException("connection refused")

        monkeypatch.setattr("producer.main.confluent_kafka.Producer", mock_producer_ctor)

        with caplog.at_level(logging.ERROR, logger="producer.main"):
            with pytest.raises(SystemExit) as exc:
                from producer import main
                import importlib
                importlib.reload(main)
                main.connect_kafka("localhost:9092", max_retries=5)
        assert exc.value.code == 1

    def test_logs_retry_lines_on_failures(self, monkeypatch, caplog):
        from confluent_kafka import KafkaException
        _apply_env(_base_env(), monkeypatch)

        attempts = {"n": 0}

        def mock_producer_ctor(*args, **kwargs):
            attempts["n"] += 1
            raise KafkaException("connection refused")

        monkeypatch.setattr("producer.main.confluent_kafka.Producer", mock_producer_ctor)

        with caplog.at_level(logging.WARNING, logger="producer.main"):
            with pytest.raises(SystemExit):
                from producer import main
                import importlib
                importlib.reload(main)
                main.connect_kafka("localhost:9092", max_retries=5, base_delay=0)

        retry_logs = [r for r in caplog.records if "retry" in r.message.lower() or "attempt" in r.message.lower() or "failed" in r.message.lower()]
        assert len(retry_logs) >= 5


# ---------------------------------------------------------------------------
# T018b – Startup log contains config summary
# ---------------------------------------------------------------------------

class TestStartupLog:
    def test_startup_log_contains_bootstrap_servers(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.INFO, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.log_startup_summary(
                bootstrap_servers="localhost:9092",
                topic="cdc-events",
                event_rate=100,
                mode="raw",
                schema_registry_url="",
            )
        assert "localhost:9092" in caplog.text

    def test_startup_log_contains_topic(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.INFO, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.log_startup_summary(
                bootstrap_servers="localhost:9092",
                topic="cdc-events",
                event_rate=100,
                mode="raw",
                schema_registry_url="",
            )
        assert "cdc-events" in caplog.text

    def test_startup_log_contains_rate(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.INFO, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.log_startup_summary(
                bootstrap_servers="localhost:9092",
                topic="cdc-events",
                event_rate=100,
                mode="raw",
                schema_registry_url="",
            )
        assert "100" in caplog.text

    def test_startup_log_contains_mode(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.INFO, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.log_startup_summary(
                bootstrap_servers="localhost:9092",
                topic="cdc-events",
                event_rate=100,
                mode="raw",
                schema_registry_url="",
            )
        assert "raw" in caplog.text.lower()


# ---------------------------------------------------------------------------
# T018c – Per-batch log contains rate=<n>/s
# ---------------------------------------------------------------------------

class TestBatchLog:
    def test_batch_log_contains_rate(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.INFO, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.log_batch_rate(achieved_rate=98.5)
        assert "rate=" in caplog.text

    def test_batch_log_contains_actual_value(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.INFO, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.log_batch_rate(achieved_rate=98.5)
        assert "98" in caplog.text


# ---------------------------------------------------------------------------
# T027 – Startup log: rate/mode/SR-url content
# ---------------------------------------------------------------------------

class TestStartupLogModeField:
    def test_startup_log_contains_mode_raw_when_no_sr_url(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.INFO, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.log_startup_summary(
                bootstrap_servers="localhost:9092",
                topic="cdc-events",
                event_rate=100,
                mode="raw",
                schema_registry_url="",
            )
        assert "mode=raw" in caplog.text

    def test_startup_log_contains_mode_schema_registry_when_sr_url_set(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.INFO, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.log_startup_summary(
                bootstrap_servers="localhost:9092",
                topic="cdc-events",
                event_rate=100,
                mode="schema-registry",
                schema_registry_url="http://sr:8081",
            )
        assert "mode=schema-registry" in caplog.text

    def test_startup_log_includes_url_when_sr_set(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.INFO, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.log_startup_summary(
                bootstrap_servers="localhost:9092",
                topic="cdc-events",
                event_rate=100,
                mode="schema-registry",
                schema_registry_url="http://sr:8081",
            )
        assert "http://sr:8081" in caplog.text

    def test_startup_log_contains_rate_per_sec(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.INFO, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.log_startup_summary(
                bootstrap_servers="localhost:9092",
                topic="cdc-events",
                event_rate=200,
                mode="raw",
                schema_registry_url="",
            )
        assert "200/s" in caplog.text

    def test_startup_log_no_url_when_sr_empty(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.INFO, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.log_startup_summary(
                bootstrap_servers="localhost:9092",
                topic="cdc-events",
                event_rate=100,
                mode="raw",
                schema_registry_url="",
            )
        assert "url=" not in caplog.text


# ---------------------------------------------------------------------------
# T018d – Rate-drift warning when achieved < 90% of target
# ---------------------------------------------------------------------------

class TestRateDriftWarning:
    def test_drift_warning_logged_when_below_90_percent(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.WARNING, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.check_rate_drift(target_rate=100, achieved_rate=85.0)
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1

    def test_no_warning_when_above_90_percent(self, monkeypatch, caplog):
        _apply_env(_base_env(), monkeypatch)
        with caplog.at_level(logging.WARNING, logger="producer.main"):
            import importlib
            from producer import main
            importlib.reload(main)
            main.check_rate_drift(target_rate=100, achieved_rate=95.0)
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 0
