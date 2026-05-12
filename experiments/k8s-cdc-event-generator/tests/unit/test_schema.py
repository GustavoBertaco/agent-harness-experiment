import pytest
import fastavro
import io


DEFAULT_TEMPLATE = """{
  "id": "uuid",
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "status": "choice(active,inactive,pending)",
  "amount": "decimal(2)",
  "description": "string(32)"
}"""


class TestBuildRowSchema:
    def test_returns_dict_with_record_type(self):
        from producer.schema import build_row_schema
        schema = build_row_schema(DEFAULT_TEMPLATE)
        assert schema["type"] == "record"

    def test_name_is_row(self):
        from producer.schema import build_row_schema
        schema = build_row_schema(DEFAULT_TEMPLATE)
        assert schema["name"] == "Row"

    def test_namespace_is_synthetic_cdc(self):
        from producer.schema import build_row_schema
        schema = build_row_schema(DEFAULT_TEMPLATE)
        assert schema["namespace"] == "synthetic.cdc"

    def test_uuid_maps_to_string(self):
        from producer.schema import build_row_schema
        schema = build_row_schema('{"id": "uuid"}')
        field = next(f for f in schema["fields"] if f["name"] == "id")
        assert field["type"] == "string"

    def test_timestamp_maps_to_long(self):
        from producer.schema import build_row_schema
        schema = build_row_schema('{"ts": "timestamp"}')
        field = next(f for f in schema["fields"] if f["name"] == "ts")
        assert field["type"] == "long"

    def test_decimal_maps_to_string(self):
        from producer.schema import build_row_schema
        schema = build_row_schema('{"amount": "decimal(2)"}')
        field = next(f for f in schema["fields"] if f["name"] == "amount")
        assert field["type"] == "string"

    def test_choice_maps_to_string(self):
        from producer.schema import build_row_schema
        schema = build_row_schema('{"status": "choice(a,b,c)"}')
        field = next(f for f in schema["fields"] if f["name"] == "status")
        assert field["type"] == "string"

    def test_string_n_maps_to_string(self):
        from producer.schema import build_row_schema
        schema = build_row_schema('{"desc": "string(32)"}')
        field = next(f for f in schema["fields"] if f["name"] == "desc")
        assert field["type"] == "string"

    def test_int_maps_to_int(self):
        from producer.schema import build_row_schema
        schema = build_row_schema('{"count": "int"}')
        field = next(f for f in schema["fields"] if f["name"] == "count")
        assert field["type"] == "int"

    def test_int_range_maps_to_int(self):
        from producer.schema import build_row_schema
        schema = build_row_schema('{"val": "int(1,100)"}')
        field = next(f for f in schema["fields"] if f["name"] == "val")
        assert field["type"] == "int"

    def test_all_7_tokens_in_default_template(self):
        from producer.schema import build_row_schema
        schema = build_row_schema(DEFAULT_TEMPLATE)
        assert len(schema["fields"]) == 6

    def test_unknown_token_exits(self):
        from producer.schema import build_row_schema
        with pytest.raises(SystemExit) as exc:
            build_row_schema('{"x": "unknown_token"}')
        assert exc.value.code == 1

    def test_invalid_avro_identifier_exits(self):
        from producer.schema import build_row_schema
        with pytest.raises(SystemExit) as exc:
            build_row_schema('{"1invalid": "int"}')
        assert exc.value.code == 1

    def test_built_schema_passes_fastavro_parse(self):
        from producer.schema import build_row_schema
        schema = build_row_schema(DEFAULT_TEMPLATE)
        parsed = fastavro.parse_schema(schema)
        assert parsed is not None


class TestBuildEnvelopeSchema:
    def test_returns_parsed_schema(self):
        from producer.schema import build_envelope_schema
        parsed = build_envelope_schema(DEFAULT_TEMPLATE)
        assert parsed is not None

    def test_envelope_has_op_field(self):
        from producer.schema import build_envelope_schema
        parsed = build_envelope_schema(DEFAULT_TEMPLATE)
        # fastavro parsed schema stores field names
        field_names = [f["name"] for f in parsed["fields"]]
        assert "op" in field_names

    def test_envelope_has_before_after_source_ts_ms_transaction(self):
        from producer.schema import build_envelope_schema
        parsed = build_envelope_schema(DEFAULT_TEMPLATE)
        field_names = [f["name"] for f in parsed["fields"]]
        for name in ("before", "after", "source", "ts_ms", "transaction"):
            assert name in field_names, f"Missing field: {name}"

    def test_envelope_schema_can_serialize_create_event(self):  # noqa: E301
        from producer.schema import build_envelope_schema
        parsed = build_envelope_schema(DEFAULT_TEMPLATE)

        row = {
            "id": "abc",
            "created_at": 1000,
            "updated_at": 1000,
            "status": "active",
            "amount": "12.34",
            "description": "test",
        }
        source = {
            "version": "1.9.7.Final",
            "connector": "mysql",
            "name": "cdc-events",
            "ts_ms": 1000,
            "db": "synthetic_db",
            "table": "events",
            "file": "binlog.000001",
            "pos": 1,
        }
        event = {
            "before": None,
            "after": ("synthetic.cdc.Row", row),
            "source": source,
            "op": "c",
            "ts_ms": 1000,
            "transaction": None,
        }
        buf = io.BytesIO()
        fastavro.schemaless_writer(buf, parsed, event)
        assert len(buf.getvalue()) > 0


# ---------------------------------------------------------------------------
# T016 – RawSerializer
# ---------------------------------------------------------------------------

def _make_envelope_event(parsed_schema):
    row = {
        "id": "abc",
        "created_at": 1000,
        "updated_at": 1000,
        "status": "active",
        "amount": "12.34",
        "description": "test_desc",
    }
    source = {
        "version": "1.9.7.Final",
        "connector": "mysql",
        "name": "cdc-events",
        "ts_ms": 1000,
        "db": "synthetic_db",
        "table": "events",
        "file": "binlog.000001",
        "pos": 1,
    }
    return {
        "before": None,
        "after": ("synthetic.cdc.Row", row),
        "source": source,
        "op": "c",
        "ts_ms": 1000,
        "transaction": None,
    }


class TestRawSerializer:
    def test_serialize_returns_bytes(self):
        from producer.schema import build_envelope_schema, RawSerializer
        schema = build_envelope_schema(DEFAULT_TEMPLATE)
        serializer = RawSerializer()
        event = _make_envelope_event(schema)
        result = serializer.serialize(event, schema)
        assert isinstance(result, bytes)

    def test_output_is_non_empty(self):
        from producer.schema import build_envelope_schema, RawSerializer
        schema = build_envelope_schema(DEFAULT_TEMPLATE)
        serializer = RawSerializer()
        event = _make_envelope_event(schema)
        result = serializer.serialize(event, schema)
        assert len(result) > 0

    def test_no_confluent_wire_prefix(self):
        # Use an update event where before is non-null (union index=1, zigzag=2=0x02).
        # Confluent wire format always starts with magic byte 0x00; raw Avro with a
        # non-null union starts with 0x02, so the two are distinguishable.
        from producer.schema import build_envelope_schema, RawSerializer
        schema = build_envelope_schema(DEFAULT_TEMPLATE)
        serializer = RawSerializer()
        row = {"id": "abc", "created_at": 1000, "updated_at": 1000,
               "status": "active", "amount": "12.34", "description": "test"}
        source = {"version": "1.9.7.Final", "connector": "mysql", "name": "cdc-events",
                  "ts_ms": 1000, "db": "synthetic_db", "table": "events",
                  "file": "binlog.000001", "pos": 1}
        event = {
            "before": ("synthetic.cdc.Row", row),
            "after": ("synthetic.cdc.Row", row),
            "source": source, "op": "u", "ts_ms": 1000, "transaction": None,
        }
        result = serializer.serialize(event, schema)
        assert result[0] != 0x00, "Raw mode with non-null before must not start with Confluent magic byte 0x00"

    def test_output_decodable_with_schemaless_reader(self):
        from producer.schema import build_envelope_schema, RawSerializer
        schema = build_envelope_schema(DEFAULT_TEMPLATE)
        serializer = RawSerializer()
        event = _make_envelope_event(schema)
        raw = serializer.serialize(event, schema)
        decoded = fastavro.schemaless_reader(io.BytesIO(raw), schema)
        assert decoded["op"] == "c"


# ---------------------------------------------------------------------------
# T023 – SchemaRegistrySerializer
# ---------------------------------------------------------------------------

class TestSchemaRegistrySerializer:
    def test_registration_called_once_in_init(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.register_schema.return_value = 42
        mocker.patch("producer.schema.SchemaRegistryClient", return_value=mock_client)

        from producer.schema import SchemaRegistrySerializer
        SchemaRegistrySerializer(url="http://sr:8081", topic="cdc-events", schema_json="{}")
        mock_client.register_schema.assert_called_once()

    def test_subject_name_is_topic_dash_value(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.register_schema.return_value = 5
        mocker.patch("producer.schema.SchemaRegistryClient", return_value=mock_client)

        from producer.schema import SchemaRegistrySerializer
        SchemaRegistrySerializer(url="http://sr:8081", topic="my-topic", schema_json="{}")
        call_args = mock_client.register_schema.call_args
        assert call_args[0][0] == "my-topic-value"

    def test_serialize_starts_with_magic_byte_0x00(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.register_schema.return_value = 7
        mocker.patch("producer.schema.SchemaRegistryClient", return_value=mock_client)

        from producer.schema import SchemaRegistrySerializer, build_envelope_schema
        schema = build_envelope_schema(DEFAULT_TEMPLATE)
        ser = SchemaRegistrySerializer(url="http://sr:8081", topic="cdc-events", schema_json="{}")
        event = _make_envelope_event(schema)
        result = ser.serialize(event, schema)
        assert result[0] == 0x00

    def test_serialize_has_4_byte_big_endian_schema_id(self, mocker):
        import struct
        mock_client = mocker.MagicMock()
        mock_client.register_schema.return_value = 42
        mocker.patch("producer.schema.SchemaRegistryClient", return_value=mock_client)

        from producer.schema import SchemaRegistrySerializer, build_envelope_schema
        schema = build_envelope_schema(DEFAULT_TEMPLATE)
        ser = SchemaRegistrySerializer(url="http://sr:8081", topic="cdc-events", schema_json="{}")
        event = _make_envelope_event(schema)
        result = ser.serialize(event, schema)
        schema_id = struct.unpack(">I", result[1:5])[0]
        assert schema_id == 42

    def test_exits_1_when_sr_raises_error_at_init(self, mocker):
        from confluent_kafka.schema_registry.error import SchemaRegistryError
        mock_client = mocker.MagicMock()
        mock_client.register_schema.side_effect = SchemaRegistryError(500, 40401, "SR unreachable")
        mocker.patch("producer.schema.SchemaRegistryClient", return_value=mock_client)

        from producer.schema import SchemaRegistrySerializer
        with pytest.raises(SystemExit) as exc:
            SchemaRegistrySerializer(url="http://sr:8081", topic="cdc-events", schema_json="{}")
        assert exc.value.code == 1


# ---------------------------------------------------------------------------
# T025 – make_serializer factory with SR URL
# ---------------------------------------------------------------------------

class TestMakeSerializerWithSR:
    def test_returns_sr_serializer_when_url_non_empty(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.register_schema.return_value = 1
        mocker.patch("producer.schema.SchemaRegistryClient", return_value=mock_client)

        from producer.schema import build_envelope_schema, make_serializer, SchemaRegistrySerializer
        from producer.config import ProducerConfig
        import os
        env = {
            "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
            "KAFKA_TOPIC": "cdc-events",
            "SCHEMA_REGISTRY_URL": "http://sr:8081",
        }
        orig = {k: os.environ.get(k) for k in env}
        for k, v in env.items():
            os.environ[k] = v
        try:
            config = ProducerConfig()
            schema = build_envelope_schema(DEFAULT_TEMPLATE)
            serializer = make_serializer(config, schema)
            assert isinstance(serializer, SchemaRegistrySerializer)
        finally:
            for k, v in orig.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_sr_serializer_has_serialize_method(self, mocker):
        mock_client = mocker.MagicMock()
        mock_client.register_schema.return_value = 1
        mocker.patch("producer.schema.SchemaRegistryClient", return_value=mock_client)

        from producer.schema import build_envelope_schema, make_serializer
        from producer.config import ProducerConfig
        import os
        env = {
            "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
            "KAFKA_TOPIC": "cdc-events",
            "SCHEMA_REGISTRY_URL": "http://sr:8081",
        }
        orig = {k: os.environ.get(k) for k in env}
        for k, v in env.items():
            os.environ[k] = v
        try:
            config = ProducerConfig()
            schema = build_envelope_schema(DEFAULT_TEMPLATE)
            serializer = make_serializer(config, schema)
            assert callable(getattr(serializer, "serialize", None))
        finally:
            for k, v in orig.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class TestMakeSerializer:
    def test_returns_raw_serializer_when_no_url(self):
        from producer.schema import build_envelope_schema, make_serializer, RawSerializer
        from producer.config import ProducerConfig
        import os
        env = {
            "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
            "KAFKA_TOPIC": "cdc-events",
            "SCHEMA_REGISTRY_URL": "",
        }
        orig = {k: os.environ.get(k) for k in env}
        for k, v in env.items():
            os.environ[k] = v
        try:
            config = ProducerConfig()
            schema = build_envelope_schema(DEFAULT_TEMPLATE)
            serializer = make_serializer(config, schema)
            assert isinstance(serializer, RawSerializer)
        finally:
            for k, v in orig.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_raw_serializer_has_serialize_method(self):
        from producer.schema import build_envelope_schema, make_serializer
        from producer.config import ProducerConfig
        import os
        env = {
            "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
            "KAFKA_TOPIC": "cdc-events",
            "SCHEMA_REGISTRY_URL": "",
        }
        orig = {k: os.environ.get(k) for k in env}
        for k, v in env.items():
            os.environ[k] = v
        try:
            config = ProducerConfig()
            schema = build_envelope_schema(DEFAULT_TEMPLATE)
            serializer = make_serializer(config, schema)
            assert callable(getattr(serializer, "serialize", None))
        finally:
            for k, v in orig.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
