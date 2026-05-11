import os
import sys
import pytest
from unittest.mock import patch


def import_config():
    import importlib
    import producer.config as mod
    importlib.reload(mod)
    return mod


class TestProducerConfigDefaults:
    def test_default_bootstrap_servers(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {}, clear=True):
            cfg = ProducerConfig()
        assert cfg.bootstrap_servers == "localhost:9092"

    def test_default_topic(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {}, clear=True):
            cfg = ProducerConfig()
        assert cfg.topic == "cdc-events"

    def test_default_event_rate(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {}, clear=True):
            cfg = ProducerConfig()
        assert cfg.event_rate == 100

    def test_default_schema_registry_url(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {}, clear=True):
            cfg = ProducerConfig()
        assert cfg.schema_registry_url == ""

    def test_default_op_weights(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {}, clear=True):
            cfg = ProducerConfig()
        assert cfg.op_weights.c == pytest.approx(70.0)
        assert cfg.op_weights.u == pytest.approx(20.0)
        assert cfg.op_weights.d == pytest.approx(10.0)


class TestProducerConfigEnvVarLoading:
    def test_loads_bootstrap_servers_from_env(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {"KAFKA_BOOTSTRAP_SERVERS": "broker:9093"}):
            cfg = ProducerConfig()
        assert cfg.bootstrap_servers == "broker:9093"

    def test_loads_topic_from_env(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {"KAFKA_TOPIC": "my-topic"}):
            cfg = ProducerConfig()
        assert cfg.topic == "my-topic"

    def test_loads_event_rate_from_env_and_coerces_to_int(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {"EVENT_RATE_PER_SEC": "500"}):
            cfg = ProducerConfig()
        assert cfg.event_rate == 500
        assert isinstance(cfg.event_rate, int)

    def test_loads_schema_registry_url_from_env(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {"SCHEMA_REGISTRY_URL": "http://sr:8081"}):
            cfg = ProducerConfig()
        assert cfg.schema_registry_url == "http://sr:8081"

    def test_loads_payload_template_from_env(self):
        from producer.config import ProducerConfig
        tmpl = '{"x": "int"}'
        with patch.dict(os.environ, {"PAYLOAD_TEMPLATE": tmpl}):
            cfg = ProducerConfig()
        assert cfg.payload_template == tmpl


class TestProducerConfigValidation:
    def test_event_rate_below_min_exits(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {"EVENT_RATE_PER_SEC": "0"}):
            with pytest.raises(SystemExit) as exc:
                ProducerConfig()
        assert exc.value.code == 1

    def test_event_rate_above_max_exits(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {"EVENT_RATE_PER_SEC": "10001"}):
            with pytest.raises(SystemExit) as exc:
                ProducerConfig()
        assert exc.value.code == 1

    def test_event_rate_boundary_min_passes(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {"EVENT_RATE_PER_SEC": "1"}):
            cfg = ProducerConfig()
        assert cfg.event_rate == 1

    def test_event_rate_boundary_max_passes(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {"EVENT_RATE_PER_SEC": "10000"}):
            cfg = ProducerConfig()
        assert cfg.event_rate == 10000

    def test_non_integer_event_rate_exits(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {"EVENT_RATE_PER_SEC": "abc"}):
            with pytest.raises(SystemExit) as exc:
                ProducerConfig()
        assert exc.value.code == 1

    def test_empty_bootstrap_servers_exits(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {"KAFKA_BOOTSTRAP_SERVERS": ""}):
            with pytest.raises(SystemExit) as exc:
                ProducerConfig()
        assert exc.value.code == 1

    def test_empty_topic_exits(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {"KAFKA_TOPIC": ""}):
            with pytest.raises(SystemExit) as exc:
                ProducerConfig()
        assert exc.value.code == 1

    def test_config_is_immutable_after_init(self):
        from producer.config import ProducerConfig
        with patch.dict(os.environ, {}, clear=True):
            cfg = ProducerConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.event_rate = 999


class TestOperationWeights:
    def test_parses_custom_weights(self):
        from producer.config import OperationWeights
        w = OperationWeights.parse("c:60,u:30,d:10")
        assert w.c == pytest.approx(60.0)
        assert w.u == pytest.approx(30.0)
        assert w.d == pytest.approx(10.0)

    def test_weights_sum_to_100_required(self):
        from producer.config import OperationWeights
        with pytest.raises(SystemExit) as exc:
            OperationWeights.parse("c:50,u:30,d:10")
        assert exc.value.code == 1

    def test_weights_sum_tolerance(self):
        from producer.config import OperationWeights
        # 70.0005 + 20.0 + 9.9995 = 100.0 — within ±0.001
        w = OperationWeights.parse("c:70.0005,u:20,d:9.9995")
        assert w.c == pytest.approx(70.0005)

    def test_unrecognized_op_token_exits(self):
        from producer.config import OperationWeights
        with pytest.raises(SystemExit) as exc:
            OperationWeights.parse("c:70,u:20,x:10")
        assert exc.value.code == 1

    def test_malformed_format_exits(self):
        from producer.config import OperationWeights
        with pytest.raises(SystemExit) as exc:
            OperationWeights.parse("bad-format")
        assert exc.value.code == 1

    def test_weights_exposed_as_floats(self):
        from producer.config import OperationWeights
        w = OperationWeights.parse("c:70,u:20,d:10")
        assert isinstance(w.c, float)
        assert isinstance(w.u, float)
        assert isinstance(w.d, float)

    def test_as_list_for_random_choices(self):
        from producer.config import OperationWeights
        w = OperationWeights.parse("c:70,u:20,d:10")
        ops, weights = w.as_choices()
        assert ops == ["c", "u", "d"]
        assert sum(weights) == pytest.approx(100.0)
