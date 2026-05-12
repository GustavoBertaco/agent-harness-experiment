import io
import json
import logging
import re
import struct
import sys

import fastavro
from confluent_kafka.schema_registry import SchemaRegistryClient, Schema
from confluent_kafka.schema_registry.error import SchemaRegistryError

logger = logging.getLogger(__name__)

_AVRO_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DECIMAL_RE = re.compile(r"^decimal\(\d+\)$")
_CHOICE_RE = re.compile(r"^choice\(.+\)$")
_STRING_N_RE = re.compile(r"^string\(\d+\)$")
_INT_RANGE_RE = re.compile(r"^int\(-?\d+,-?\d+\)$")


def _token_to_avro_type(token: str) -> str:
    if token == "uuid":
        return "string"
    if token == "timestamp":
        return "long"
    if token == "int":
        return "int"
    if _DECIMAL_RE.match(token):
        return "string"
    if _CHOICE_RE.match(token):
        return "string"
    if _STRING_N_RE.match(token):
        return "string"
    if _INT_RANGE_RE.match(token):
        return "int"
    logger.error("Unknown generator token: %r", token)
    sys.exit(1)


def build_row_schema(payload_template_json: str) -> dict:
    try:
        template = json.loads(payload_template_json)
    except json.JSONDecodeError as e:
        logger.error("PAYLOAD_TEMPLATE is not valid JSON: %s", e)
        sys.exit(1)

    fields = []
    for field_name, token in template.items():
        if not _AVRO_IDENTIFIER_RE.match(field_name):
            logger.error("Invalid Avro field name: %r", field_name)
            sys.exit(1)
        avro_type = _token_to_avro_type(token)
        fields.append({"name": field_name, "type": avro_type})

    return {
        "type": "record",
        "name": "Row",
        "namespace": "synthetic.cdc",
        "fields": fields,
    }


def _build_source_schema() -> dict:
    return {
        "type": "record",
        "name": "Source",
        "namespace": "synthetic.cdc",
        "fields": [
            {"name": "version",   "type": "string"},
            {"name": "connector", "type": "string"},
            {"name": "name",      "type": "string"},
            {"name": "ts_ms",     "type": "long"},
            {"name": "db",        "type": "string"},
            {"name": "table",     "type": "string"},
            {"name": "file",      "type": "string"},
            {"name": "pos",       "type": "long"},
        ],
    }


def _build_raw_envelope_schema(payload_template_json: str) -> dict:
    row_schema = build_row_schema(payload_template_json)
    source_schema = _build_source_schema()
    return {
        "type": "record",
        "name": "Envelope",
        "namespace": "synthetic.cdc",
        "fields": [
            {"name": "before", "type": ["null", row_schema], "default": None},
            {"name": "after",  "type": ["null", "synthetic.cdc.Row"], "default": None},
            {"name": "source", "type": source_schema},
            {"name": "op",     "type": "string"},
            {"name": "ts_ms",  "type": "long"},
            {"name": "transaction", "type": ["null", "string"], "default": None},
        ],
    }


def build_envelope_schema(payload_template_json: str):
    return fastavro.parse_schema(_build_raw_envelope_schema(payload_template_json))


class RawSerializer:
    def serialize(self, event: dict, schema) -> bytes:
        buf = io.BytesIO()
        fastavro.schemaless_writer(buf, schema, event)
        return buf.getvalue()


class SchemaRegistrySerializer:
    def __init__(self, url: str, topic: str, schema_json: str) -> None:
        try:
            client = SchemaRegistryClient({"url": url})
            sr_schema = Schema(schema_json, "AVRO")
            self._schema_id: int = client.register_schema(f"{topic}-value", sr_schema)
        except SchemaRegistryError as exc:
            logger.error("Schema Registry unavailable: %s", exc)
            sys.exit(1)

    def serialize(self, event: dict, schema) -> bytes:
        buf = io.BytesIO()
        buf.write(b"\x00")
        buf.write(struct.pack(">I", self._schema_id))
        fastavro.schemaless_writer(buf, schema, event)
        return buf.getvalue()


def make_serializer(config, schema):
    if config.schema_registry_url:
        raw_schema = _build_raw_envelope_schema(config.payload_template)
        return SchemaRegistrySerializer(
            url=config.schema_registry_url,
            topic=config.topic,
            schema_json=json.dumps(raw_schema),
        )
    return RawSerializer()
