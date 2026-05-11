import random
import re
import string
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

_DECIMAL_RE = re.compile(r"^decimal\((\d+)\)$")
_CHOICE_RE = re.compile(r"^choice\((.+)\)$")
_STRING_N_RE = re.compile(r"^string\((\d+)\)$")
_INT_RANGE_RE = re.compile(r"^int\((-?\d+),(-?\d+)\)$")

_ALPHANUM = string.ascii_letters + string.digits


def _generate_value(token: str) -> Any:
    if token == "uuid":
        return str(uuid.uuid4())
    if token == "timestamp":
        return int(time.time() * 1000)
    if token == "int":
        return random.randint(0, 2**31 - 1)
    m = _DECIMAL_RE.match(token)
    if m:
        places = int(m.group(1))
        integer_part = random.randint(0, 9999)
        frac_part = random.randint(0, 10**places - 1)
        return f"{integer_part}.{frac_part:0{places}d}"
    m = _CHOICE_RE.match(token)
    if m:
        options = [o.strip() for o in m.group(1).split(",")]
        return random.choice(options)
    m = _STRING_N_RE.match(token)
    if m:
        n = int(m.group(1))
        return "".join(random.choices(_ALPHANUM, k=n))
    m = _INT_RANGE_RE.match(token)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return random.randint(lo, hi)
    raise ValueError(f"Unknown generator token: {token!r}")


def generate_row(schema_fields: List[Dict], payload_template: Dict) -> Dict:
    return {field["name"]: _generate_value(payload_template[field["name"]]) for field in schema_fields}


def generate_source(topic: str, pos: int) -> Dict:
    return {
        "version": "1.9.7.Final",
        "connector": "mysql",
        "name": topic,
        "ts_ms": int(time.time() * 1000),
        "db": "synthetic_db",
        "table": "events",
        "file": "binlog.000001",
        "pos": pos,
    }


def generate_event(
    op: str,
    schema_fields: List[Dict],
    payload_template: Dict,
    source_pos: int,
    ts_ms: int,
) -> Dict:
    source = generate_source(payload_template.get("__topic__", "cdc-events"), source_pos)
    source["ts_ms"] = ts_ms

    def _row() -> Tuple[str, Dict]:
        return ("synthetic.cdc.Row", generate_row(schema_fields, payload_template))

    if op == "c":
        before: Optional[Tuple] = None
        after: Optional[Tuple] = _row()
    elif op == "u":
        before = _row()
        after = _row()
    elif op == "d":
        before = _row()
        after = None
    else:  # "r" snapshot
        before = None
        after = _row()

    return {
        "before": before,
        "after": after,
        "source": source,
        "op": op,
        "ts_ms": ts_ms,
        "transaction": None,
    }
