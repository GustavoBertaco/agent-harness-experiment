import time
import pytest

DEFAULT_TEMPLATE = """{
  "id": "uuid",
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "status": "choice(active,inactive,pending)",
  "amount": "decimal(2)",
  "description": "string(32)"
}"""


# ---------------------------------------------------------------------------
# T012 – Row generation
# ---------------------------------------------------------------------------

class TestGenerateRow:
    def _schema_fields(self, template_json):
        from producer.schema import build_row_schema
        schema = build_row_schema(template_json)
        return schema["fields"]

    def test_uuid_produces_string(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"id": "uuid"}')
        row = generate_row(fields, {"id": "uuid"})
        assert isinstance(row["id"], str)

    def test_uuid_format(self):
        import re
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"id": "uuid"}')
        row = generate_row(fields, {"id": "uuid"})
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            row["id"],
        )

    def test_timestamp_produces_int(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"ts": "timestamp"}')
        row = generate_row(fields, {"ts": "timestamp"})
        assert isinstance(row["ts"], int)

    def test_timestamp_is_epoch_millis(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"ts": "timestamp"}')
        row = generate_row(fields, {"ts": "timestamp"})
        now_ms = int(time.time() * 1000)
        assert abs(row["ts"] - now_ms) < 5000

    def test_decimal_produces_string(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"amount": "decimal(2)"}')
        row = generate_row(fields, {"amount": "decimal(2)"})
        assert isinstance(row["amount"], str)

    def test_decimal_has_correct_decimal_places(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"amount": "decimal(3)"}')
        row = generate_row(fields, {"amount": "decimal(3)"})
        _, decimals = row["amount"].split(".")
        assert len(decimals) == 3

    def test_choice_produces_string(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"status": "choice(active,inactive,pending)"}')
        row = generate_row(fields, {"status": "choice(active,inactive,pending)"})
        assert isinstance(row["status"], str)

    def test_choice_value_in_options(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"status": "choice(active,inactive,pending)"}')
        row = generate_row(fields, {"status": "choice(active,inactive,pending)"})
        assert row["status"] in ("active", "inactive", "pending")

    def test_string_n_produces_string(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"desc": "string(16)"}')
        row = generate_row(fields, {"desc": "string(16)"})
        assert isinstance(row["desc"], str)

    def test_string_n_has_correct_length(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"desc": "string(16)"}')
        row = generate_row(fields, {"desc": "string(16)"})
        assert len(row["desc"]) == 16

    def test_int_produces_int(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"count": "int"}')
        row = generate_row(fields, {"count": "int"})
        assert isinstance(row["count"], int)

    def test_int_range_produces_int(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"val": "int(5,10)"}')
        row = generate_row(fields, {"val": "int(5,10)"})
        assert isinstance(row["val"], int)

    def test_int_range_within_bounds(self):
        from producer.event_generator import generate_row
        fields = self._schema_fields('{"val": "int(5,10)"}')
        for _ in range(20):
            row = generate_row(fields, {"val": "int(5,10)"})
            assert 5 <= row["val"] <= 10

    def test_field_count_matches_template(self):
        import json
        from producer.event_generator import generate_row
        fields = self._schema_fields(DEFAULT_TEMPLATE)
        template = json.loads(DEFAULT_TEMPLATE)
        row = generate_row(fields, template)
        assert len(row) == len(template)

    def test_all_field_names_are_valid_avro_identifiers(self):
        import re
        import json
        from producer.event_generator import generate_row
        fields = self._schema_fields(DEFAULT_TEMPLATE)
        template = json.loads(DEFAULT_TEMPLATE)
        row = generate_row(fields, template)
        pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        for key in row:
            assert pattern.match(key), f"Invalid Avro identifier: {key!r}"


# ---------------------------------------------------------------------------
# T013 – Source record
# ---------------------------------------------------------------------------

class TestGenerateSource:
    def test_version_constant(self):
        from producer.event_generator import generate_source
        src = generate_source("cdc-events", 0)
        assert src["version"] == "1.9.7.Final"

    def test_connector_constant(self):
        from producer.event_generator import generate_source
        src = generate_source("cdc-events", 0)
        assert src["connector"] == "mysql"

    def test_db_constant(self):
        from producer.event_generator import generate_source
        src = generate_source("cdc-events", 0)
        assert src["db"] == "synthetic_db"

    def test_table_constant(self):
        from producer.event_generator import generate_source
        src = generate_source("cdc-events", 0)
        assert src["table"] == "events"

    def test_file_constant(self):
        from producer.event_generator import generate_source
        src = generate_source("cdc-events", 0)
        assert src["file"] == "binlog.000001"

    def test_name_matches_topic(self):
        from producer.event_generator import generate_source
        src = generate_source("my-topic", 0)
        assert src["name"] == "my-topic"

    def test_pos_non_negative(self):
        from producer.event_generator import generate_source
        src = generate_source("cdc-events", 0)
        assert src["pos"] >= 0

    def test_pos_strictly_increasing(self):
        from producer.event_generator import generate_source
        positions = [generate_source("cdc-events", i)["pos"] for i in range(5)]
        assert positions == sorted(positions)
        assert len(positions) == len(set(positions))

    def test_ts_ms_within_5_seconds_of_now(self):
        from producer.event_generator import generate_source
        now_ms = int(time.time() * 1000)
        src = generate_source("cdc-events", 0)
        assert abs(src["ts_ms"] - now_ms) < 5000


# ---------------------------------------------------------------------------
# T014 – CDC Event before/after nullability + OperationWeights sampling
# ---------------------------------------------------------------------------

class TestGenerateEvent:
    def _make_schema_and_template(self):
        import json
        from producer.schema import build_row_schema
        template = json.loads(DEFAULT_TEMPLATE)
        fields = build_row_schema(DEFAULT_TEMPLATE)["fields"]
        return fields, template

    def test_create_op_before_is_null(self):
        from producer.event_generator import generate_event
        fields, template = self._make_schema_and_template()
        event = generate_event("c", fields, template, 0, int(time.time() * 1000))
        assert event["before"] is None

    def test_create_op_after_is_row(self):
        from producer.event_generator import generate_event
        fields, template = self._make_schema_and_template()
        event = generate_event("c", fields, template, 0, int(time.time() * 1000))
        assert event["after"] is not None
        _, row = event["after"]
        assert isinstance(row, dict)

    def test_update_op_before_is_row(self):
        from producer.event_generator import generate_event
        fields, template = self._make_schema_and_template()
        event = generate_event("u", fields, template, 0, int(time.time() * 1000))
        assert event["before"] is not None
        _, row = event["before"]
        assert isinstance(row, dict)

    def test_update_op_after_is_row(self):
        from producer.event_generator import generate_event
        fields, template = self._make_schema_and_template()
        event = generate_event("u", fields, template, 0, int(time.time() * 1000))
        assert event["after"] is not None
        _, row = event["after"]
        assert isinstance(row, dict)

    def test_delete_op_before_is_row(self):
        from producer.event_generator import generate_event
        fields, template = self._make_schema_and_template()
        event = generate_event("d", fields, template, 0, int(time.time() * 1000))
        assert event["before"] is not None
        _, row = event["before"]
        assert isinstance(row, dict)

    def test_delete_op_after_is_null(self):
        from producer.event_generator import generate_event
        fields, template = self._make_schema_and_template()
        event = generate_event("d", fields, template, 0, int(time.time() * 1000))
        assert event["after"] is None

    def test_read_op_before_is_null(self):
        from producer.event_generator import generate_event
        fields, template = self._make_schema_and_template()
        event = generate_event("r", fields, template, 0, int(time.time() * 1000))
        assert event["before"] is None

    def test_read_op_after_is_row(self):
        from producer.event_generator import generate_event
        fields, template = self._make_schema_and_template()
        event = generate_event("r", fields, template, 0, int(time.time() * 1000))
        assert event["after"] is not None

    def test_event_has_op_field(self):
        from producer.event_generator import generate_event
        fields, template = self._make_schema_and_template()
        event = generate_event("c", fields, template, 0, int(time.time() * 1000))
        assert event["op"] == "c"

    def test_event_has_ts_ms_field(self):
        from producer.event_generator import generate_event
        fields, template = self._make_schema_and_template()
        ts = int(time.time() * 1000)
        event = generate_event("c", fields, template, 0, ts)
        assert event["ts_ms"] == ts

    def test_event_transaction_is_none(self):
        from producer.event_generator import generate_event
        fields, template = self._make_schema_and_template()
        event = generate_event("c", fields, template, 0, int(time.time() * 1000))
        assert event["transaction"] is None


class TestOperationWeightsSampling:
    def test_default_distribution_c_approx_70(self):
        import random
        from producer.config import OperationWeights
        weights = OperationWeights.parse("c:70,u:20,d:10")
        ops, w = weights.as_choices()
        samples = random.choices(ops, weights=w, k=10000)
        c_pct = samples.count("c") / 100
        assert abs(c_pct - 70) < 3, f"c%={c_pct:.1f}"

    def test_default_distribution_u_approx_20(self):
        import random
        from producer.config import OperationWeights
        weights = OperationWeights.parse("c:70,u:20,d:10")
        ops, w = weights.as_choices()
        samples = random.choices(ops, weights=w, k=10000)
        u_pct = samples.count("u") / 100
        assert abs(u_pct - 20) < 3, f"u%={u_pct:.1f}"

    def test_default_distribution_d_approx_10(self):
        import random
        from producer.config import OperationWeights
        weights = OperationWeights.parse("c:70,u:20,d:10")
        ops, w = weights.as_choices()
        samples = random.choices(ops, weights=w, k=10000)
        d_pct = samples.count("d") / 100
        assert abs(d_pct - 10) < 3, f"d%={d_pct:.1f}"

    def test_weights_sum_to_100_validation(self):
        from producer.config import OperationWeights
        with pytest.raises(SystemExit) as exc:
            OperationWeights.parse("c:70,u:20,d:15")
        assert exc.value.code == 1
