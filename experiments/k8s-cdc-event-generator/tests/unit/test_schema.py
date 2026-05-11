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

    def test_envelope_schema_can_serialize_create_event(self):
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
