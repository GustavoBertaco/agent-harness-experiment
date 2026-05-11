import io
import json
import logging
import re
import sys

import fastavro

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


def build_envelope_schema(payload_template_json: str):
    row_schema = build_row_schema(payload_template_json)
    source_schema = _build_source_schema()

    envelope = {
        "type": "record",
        "name": "Envelope",
        "namespace": "synthetic.cdc",
        "fields": [
            {
                "name": "before",
                "type": ["null", row_schema],
                "default": None,
            },
            {
                "name": "after",
                "type": ["null", "synthetic.cdc.Row"],
                "default": None,
            },
            {
                "name": "source",
                "type": source_schema,
            },
            {
                "name": "op",
                "type": "string",
            },
            {
                "name": "ts_ms",
                "type": "long",
            },
            {
                "name": "transaction",
                "type": ["null", "string"],
                "default": None,
            },
        ],
    }
    return fastavro.parse_schema(envelope)
